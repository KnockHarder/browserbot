import asyncio
from typing import Any, Optional

from langchain.prompts import BasePromptTemplate

from browser import Browser, get_browser
from browser_dom import PageNode, NodePseudoType
from browser_page import BrowserPage

HOME_PAGE = 'https://chat.openai.com'
FIND_NODE_TIMEOUT = 1
ANSWER_WAIT_INTERVAL = 1


class ChatGptPage:
    _page: BrowserPage

    def __init__(self, browser: Optional[Browser] = None):
        if not browser:
            browser = get_browser()
        self.browser = browser

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
        node = await self._query_single_d('//span//button[contains(@class, "text-token-text-primary")][last()]')
        await node.click()

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
        chats = []
        page = await self.ensure_page()
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
        contents = []
        page = await self.ensure_page()
        contents += await page.query_nodes_by_xpath(f'{chat.x_path}//p', FIND_NODE_TIMEOUT)
        contents += await page.query_nodes_by_xpath(f'{chat.x_path}//li', FIND_NODE_TIMEOUT)
        contents += await page.query_nodes_by_xpath(f'{chat.x_path}//code', FIND_NODE_TIMEOUT)
        return contents and all(self.is_finished(x) for x in contents)

    @staticmethod
    def is_finished(message_node: PageNode):
        return (message_node.pseudo_type == NodePseudoType.BEFORE
                or message_node.pseudo_type == NodePseudoType.AFTER)

    async def clear_histories(self):
        page = await self.ensure_page()
        dir_nodes = await page.query_nodes_by_xpath('//h3', FIND_NODE_TIMEOUT)
        for node in dir_nodes:
            history_area = await self._query_single_d(f'{node.x_path}/../..')
            chats = await page.query_nodes_by_xpath(f'{history_area.x_path}//li', FIND_NODE_TIMEOUT)
            for chat in chats:
                await chat.click()
                button = await self._query_single_d(f'{history_area.x_path}//button[1]')
                await button.click()
                button = await self._query_single_d('//div[@role="menuitem"][text()="Delete chat"][1]')
                await button.click()
                button = await self._query_single_d('//div[contains(@class, "absolute"]//button[text()="Delete"][1]')
                await button.click()


def main():
    page = ChatGptPage()
    page.new_chat()


if __name__ == '__main__':
    main()