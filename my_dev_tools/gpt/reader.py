import asyncio
import os.path
from typing import Callable, Coroutine, Any

from bs4 import BeautifulSoup
from langchain import prompts
from transformers import AutoTokenizer

from ..browser import get_browser
from ..browser_dom import PageNode
from ..browser_page import BrowserPage
from ..gpt import ChatGptPage

ARTICLE_READ_TIMEOUT = 5


class Article:
    def __init__(self, title: str, plain_content: str, url: str = None):
        self.name = title.strip()
        self.content = plain_content
        self.url = url


async def get_paragraphs_text(node: PageNode, tag_name: str) -> str:
    root_tag = BeautifulSoup(await node.outer_html, 'html.parser')
    paragraphs = root_tag.find_all(tag_name)
    paragraphs = [x.get_text() for x in paragraphs if not x.find_all(tag_name)]
    return '\n'.join(paragraphs)


def token_size(text: str):
    if not text:
        return 0
    tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
    tokens = tokenizer.tokenize(text)
    return len(tokens)


async def summarize_article(gpt_page: ChatGptPage, article: Article):
    content_token = token_size(article.content)
    if not content_token:
        print(f"{article.name} has empty paragraph text")
        return
    template_dir = os.path.expanduser('~/.my_py_datas/chatgpt/templates')
    instruction_prompt = prompts.load_prompt(os.path.join(template_dir, '文章阅读_指令.json'))
    part_content_prompt = prompts.load_prompt(os.path.join(template_dir, '文章阅读_partContent.json'))
    end_content_prompt = prompts.load_prompt(os.path.join(template_dir, '文章阅读_endContent.json'))

    prompt_token_size = max([token_size(part_content_prompt.format(content='')),
                             token_size(end_content_prompt.format(caption='', url='', content=''))])
    token_limit = 4096 - prompt_token_size
    await gpt_page.ask_as_new_chat_and_wait(instruction_prompt.format(article_name=article.name))
    text_len_limit = int(len(article.content) / content_token * token_limit)
    text = ''
    for line in article.content.split('\n'):
        if len(line) > text_len_limit:
            raise Exception('To long paragraph', f'{line[:20]}...{line[-20:]}')
        if len(text) + len(line) > 4096:
            await gpt_page.continue_ask_and_wait(part_content_prompt.format(content=text))
            text = line
        else:
            text = '\n'.join([text, line])
    if text:
        question = end_content_prompt.format(caption=article.name, url=article.url, content=text)
        await gpt_page.continue_ask_and_wait(question)


async def read_info_q_article(page: BrowserPage) -> Article:
    title_node = await page.require_single_node_by_xpath('(//h1)[1]', ARTICLE_READ_TIMEOUT)
    content_node = await page.require_single_node_by_xpath(
        '//*[@class="content-main"]//*[@class="article-preview"][1]', ARTICLE_READ_TIMEOUT)
    return Article(await title_node.text_content,
                   await get_paragraphs_text(content_node, 'p'))


async def read_weixin_article(page: BrowserPage) -> Article:
    content_ele = await page.require_single_node_by_xpath('//*[@id="js_content"][1]', ARTICLE_READ_TIMEOUT)
    section = await get_paragraphs_text(content_ele, 'section')
    p = await get_paragraphs_text(content_ele, 'p')
    title_node = await page.require_single_node_by_xpath('//h1[1]', ARTICLE_READ_TIMEOUT)
    return Article(await title_node.text_content, p if len(p) > len(section) else section)


async def read_all_page_articles(gpt_page: ChatGptPage, article_url_prefix,
                                 article_content_func: Callable[[BrowserPage], Coroutine[Any, Any, Article]]):
    browser = get_browser()
    page_list = browser.find_pages_by_url_prefix(article_url_prefix)
    if not page_list:
        print('Cannot find any article tab', article_url_prefix)
        return
    while page_list:
        page = page_list.pop()
        article = await article_content_func(page)
        article.url = page.url
        if not article.name or not article.content:
            print('No title or paragraph content', page.url)
            continue
        await summarize_article(gpt_page, article)
        page.close()


def main():
    async def _do():
        await read_all_page_articles(page, 'https://mp.weixin.qq.com/s/', read_weixin_article)
        await read_all_page_articles(page, 'https://mp.weixin.qq.com/s?', read_weixin_article)
        await read_all_page_articles(page, 'https://www.infoq.cn/article', read_info_q_article)
        await read_all_page_articles(page, 'https://www.infoq.cn/news/', read_info_q_article)

    page = ChatGptPage()
    asyncio.get_event_loop().run_until_complete(_do())


if __name__ == '__main__':
    main()
