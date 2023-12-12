import asyncio
import os
from typing import Any, Optional, Callable, Coroutine

from langchain import prompts
from langchain.prompts import BasePromptTemplate
from transformers import AutoTokenizer

from .reader import Article, extract_weixin_article, extract_info_q_article
from ..browser import Browser, get_browser
from ..browser_dom import PageNode
from ..browser_page import BrowserPage, CommandException

HOME_PAGE = 'https://chat.openai.com'
FIND_NODE_TIMEOUT = 2
ANSWER_WAIT_INTERVAL = 1


class UnsupportedArticleUrlPrefix(Exception):
    def __init__(self, prefix: str):
        super().__init__(f'Unsupported article url prefix: {prefix}')


def _token_size(text: str):
    if not text:
        return 0
    tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
    tokens = tokenizer.tokenize(text)
    return len(tokens)


class ChatGptPage:

    def __init__(self, browser: Optional[Browser] = None):
        if not browser:
            browser = get_browser()
        self.browser = browser
        self._page: Optional[BrowserPage] = None

    async def ensure_page(self):
        if not self._page:
            self._page = await self.browser.find_or_open(HOME_PAGE)
        return self._page

    async def activate(self):
        page = await self.ensure_page()
        await page.activate()

    async def _query_single_d(self, xpath: str) -> PageNode:
        page = await self.ensure_page()
        return await page.require_single_node_by_xpath(xpath, FIND_NODE_TIMEOUT)

    async def new_chat(self):
        node = await self._query_single_d('(//span//button[contains(@class, "text-token-text-primary")])[last()]')
        await node.js_click()

    async def ask_as_new_chat(self, ques: str):
        await self.new_chat()
        await self._ask(ques)

    async def _ask(self, ques: str):
        node = await self._query_single_d('//*[@id="prompt-textarea"][last()]')
        await node.submit_input(ques)
        await node.update_node()
        while (await node.text_content).strip():
            await node.trigger_entry_key()

    async def ask_as_new_chat_and_wait(self, question: str):
        await self.ask_as_new_chat(question)
        await self._wait_answer_done()

    async def continue_ask_and_wait(self, question: str):
        page = await self.ensure_page()
        messages = await page.query_nodes_by_xpath('//main//div[contains(@class, "text-token-text-primary")]',
                                                   FIND_NODE_TIMEOUT)
        await self._ask(question)
        await self._wait_answer_done(len(messages))

    async def gen_code_question(self, prompt: BasePromptTemplate, **kwargs: Any):
        page = await self.ensure_page()
        await self.ask_as_new_chat(prompt.format(**kwargs))
        chats = await self._wait_answer_done()
        codes = await page.query_nodes_by_xpath(f'{chats[-1].x_path}//code', FIND_NODE_TIMEOUT)
        if codes:
            text = ('\n' * 2).join([await x.text_content for x in codes])
        else:
            text = await chats[-1].text_content
        return text

    async def _wait_answer_done(self, before_ask_size=0) -> list[PageNode]:
        main_ele = await self._query_single_d('//div[@id="__next"]//main[1]')
        page = await self.ensure_page()
        chats = []
        while (not chats
               or len(chats) < before_ask_size + 2
               or not (await self.is_answer_finished(chats[-1]))):
            chats = await page.query_nodes_by_xpath(
                f'{main_ele.x_path}//div[contains(@class, "text-token-text-primary")]', FIND_NODE_TIMEOUT)
            await asyncio.sleep(ANSWER_WAIT_INTERVAL)
        return chats

    async def is_answer_finished(self, chat: PageNode):
        if not await chat.text_content:
            return False
        content_nodes = list[PageNode]()
        page = await self.ensure_page()
        content_nodes += await page.query_nodes_by_xpath(f'{chat.x_path}//p', 0)
        content_nodes += await page.query_nodes_by_xpath(f'{chat.x_path}//li', 0)
        content_nodes += await page.query_nodes_by_xpath(f'{chat.x_path}//code', 0)
        if not content_nodes:
            return False
        any_pseudo_text = False
        for node, pseudo_node in [(node, pseudo_node) for node in content_nodes for pseudo_node in node.pseudo_nodes]:
            try:
                text = await pseudo_node.text_content
                if 'before' not in text:
                    any_pseudo_text = True
                    break
            except CommandException:
                pass
        return not any_pseudo_text

    async def clear_histories(self):
        page = await self.ensure_page()
        dir_nodes = await page.query_nodes_by_xpath('//h3', FIND_NODE_TIMEOUT)
        for node in dir_nodes:
            history_area = await self._query_single_d(f'{node.x_path}/../..')
            chats = await page.query_nodes_by_xpath(f'{history_area.x_path}//li//a', FIND_NODE_TIMEOUT)
            for chat in chats:
                await chat.js_click()
                button = await self._query_single_d(f'{history_area.x_path}//button')
                await button.left_click()
                button = await self._query_single_d('//div[@role="menuitem" and text()="Delete chat"][1]')
                await button.js_click()
                button = await self._query_single_d('//div[@role="dialog"]//button[div[text()="Delete"]][1]')
                await button.js_click()

    async def summarize_article(self, article: Article):
        content_token = _token_size(article.content)
        if not content_token:
            return
        template_dir = os.path.expanduser('~/.my_py_datas/chatgpt/templates')
        instruction_prompt = prompts.load_prompt(os.path.join(template_dir, '文章阅读_指令.json'))
        part_content_prompt = prompts.load_prompt(os.path.join(template_dir, '文章阅读_partContent.json'))
        end_content_prompt = prompts.load_prompt(os.path.join(template_dir, '文章阅读_endContent.json'))

        prompt_token_size = max([_token_size(part_content_prompt.format(content='')),
                                 _token_size(end_content_prompt.format(caption='', url='', content=''))])
        token_limit = 4096 - prompt_token_size
        await self.ask_as_new_chat_and_wait(instruction_prompt.format(article_name=article.name))
        text_len_limit = int(len(article.content) / content_token * token_limit)
        text = ''
        for line in article.content.split('\n'):
            if len(line) > text_len_limit:
                raise Exception('To long paragraph', f'{line[:20]}...{line[-20:]}')
            if len(text) + len(line) > 4096:
                await self.continue_ask_and_wait(part_content_prompt.format(content=text))
                text = line
            else:
                text = '\n'.join([text, line])
        if text:
            question = end_content_prompt.format(caption=article.name, url=article.url, content=text)
            await self.continue_ask_and_wait(question)

    async def _read_all_page_articles(self, article_url_prefix,
                                      article_content_func: Callable[[BrowserPage], Coroutine[Any, Any, Article]]):
        browser = get_browser()
        page_list = browser.find_pages_by_url_prefix(article_url_prefix)
        if not page_list:
            return
        while page_list:
            page = page_list.pop()
            article = await article_content_func(page)
            article.url = page.url
            if not article.name or not article.content:
                continue
            await self.summarize_article(article)
            page.close()

    async def read_articles(self):
        await self._read_all_page_articles('https://mp.weixin.qq.com/s/', extract_weixin_article)
        await self._read_all_page_articles('https://mp.weixin.qq.com/s?', extract_weixin_article)
        await self._read_all_page_articles('https://www.infoq.cn/article', extract_info_q_article)
        await self._read_all_page_articles('https://www.infoq.cn/news/', extract_info_q_article)


def main():
    page = ChatGptPage()
    asyncio.get_event_loop().run_until_complete(page.clear_histories())


if __name__ == '__main__':
    main()
