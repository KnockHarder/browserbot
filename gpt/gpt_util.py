import asyncio
import time
from typing import Any

from bs4 import BeautifulSoup
from langchain.prompts import BasePromptTemplate

from browser import Browser, ElementNotFoundError, PageElement

HOME_PAGE = 'https://chat.openai.com'


def start_new_chat(browser: Browser, activate=False):
    browser.find_and_switch(HOME_PAGE, activate)
    browser.search_elements('tag:a@@text()=New Chat')[0].click()


def ask_as_new_chat(browser: Browser, ques: str):
    start_new_chat(browser)
    continue_ask(browser, ques)


def continue_ask(browser: Browser, ques: str):
    browser.search_elements('#prompt-textarea')[0].submit_input(ques)


async def gen_code_question(browser: Browser, prompt: BasePromptTemplate, **kwargs: Any):
    browser.find_and_switch(HOME_PAGE)
    ask_as_new_chat(browser, prompt.format(**kwargs))

    main_ele = None
    while not main_ele:
        main_ele = (await browser.async_search_elements('css:#__next main')).first()
    chats = []
    while (not chats
           or len(chats) <
           2 or not (await is_answer_finished(chats[-1]))):
        chats = await main_ele.async_search_elements('css: div.text-token-text-primary')
        await asyncio.sleep(1)
    codes = (await chats[-1].async_search_elements('tag:code'))
    if codes:
        text = ('\n'*2).join([BeautifulSoup(x.html, 'html.parser').get_text() for x in codes])
    else:
        text = BeautifulSoup(chats[-1].html, 'html.parser').get_text()
    code_text = text
    return code_text


async def is_answer_finished(element: PageElement):
    if not element.text:
        return False
    contents = []
    contents += await element.async_search_elements('tag:p', timeout=0)
    contents += await element.async_search_elements('tag:li', timeout=0)
    contents += await element.async_search_elements('tag:code', timeout=0)
    return contents and all(is_element_finished(x) for x in contents)


def is_element_finished(element: PageElement):
    if element.pseudo_before == element.pseudo_after == '"`"':
        return True
    return element.pseudo_after == 'none'


def clear_chat_history(browser: Browser):
    browser.find_and_switch(HOME_PAGE)
    end = time.perf_counter() + 5
    chat_list = browser.search_elements(
        'tag:h2@text()=Chat history', end - time.perf_counter()
    ).search_after_siblings_nodes(
        'tag:nav', end - time.perf_counter()
    )[0].search_elements('tag:li', end - time.perf_counter())
    if not chat_list:
        raise ElementNotFoundError('NoChat')
    for chat in chat_list:
        chat.search_elements('tag:a')[0].click()
        chat.search_elements('tag:button')[1].click()
        browser.search_elements('tag:button@text()=Delete')[0].click()


def ask_as_new_chat_and_wait(browser: Browser, question: str):
    ask_as_new_chat(browser, question)
    _wait_answer_done(browser)


def continue_ask_and_wait(browser: Browser, question: str):
    message_size = len(browser.search_elements('css:main div.text-token-text-primary'))
    continue_ask(browser, question)
    _wait_answer_done(browser, message_size)


def _wait_answer_done(browser: Browser, before_ask_size=0):
    messages = browser.search_elements('css:main div.text-token-text-primary')
    while len(messages) < before_ask_size + 2:
        time.sleep(0.1)
    answer = browser.search_elements('css:main div.text-token-text-primary')[-1]
    while not (answer.text
               or not answer.search_elements('tag:p')
               or any(x.pseudo_after != 'none' for x in answer.search_elements('tag:p'))
               or any(x.pseudo_after != 'none' for x in answer.search_elements('tag:li'))):
        answer = browser.search_elements('css:main div.text-token-text-primary')[-1]
        time.sleep(0.1)


if __name__ == '__main__':
    ask_as_new_chat_and_wait(Browser(), '最近有什么科技新闻吗？')
