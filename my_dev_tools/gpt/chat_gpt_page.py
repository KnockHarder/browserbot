import asyncio
from typing import Any, Optional

from langchain.prompts import BasePromptTemplate

from ..browser import Browser, get_browser
from ..browser_dom import PageNode
from ..browser_page import BrowserPage, CommandException

HOME_PAGE = 'https://chat.openai.com'
FIND_NODE_TIMEOUT = 2
ANSWER_WAIT_INTERVAL = 1


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


def main():
    page = ChatGptPage()
    asyncio.get_event_loop().run_until_complete(page.clear_histories())


if __name__ == '__main__':
    main()
