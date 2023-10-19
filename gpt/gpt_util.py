import asyncio
import time
from typing import Any

from bs4 import BeautifulSoup
from langchain import BasePromptTemplate

from browser import Browser, ElementNotFoundError

HOME_PAGE = 'https://chat.openai.com'


def start_new_chat(browser: Browser):
    browser.find_and_switch(HOME_PAGE)
    browser.search_elements('tag:a@@text()=New Chat')[0].click()


def ask_as_new_chat(browser: Browser, ques: str):
    start_new_chat(browser)
    continue_ask(browser, ques)


def continue_ask(browser: Browser, ques: str):
    browser.search_elements('#prompt-textarea')[0].submit_input(ques)


async def gen_code_question(browser: Browser, prompt: BasePromptTemplate, **kwargs: Any):
    browser.find_and_switch(HOME_PAGE)
    ask_as_new_chat(browser, prompt.format(**kwargs))
    while True:
        try:
            code_ele = browser.search_elements(
                'css:#__next main div.text-token-text-primary code', timeout=0.1)[0]
            if code_ele.pseudo_after == 'none':
                break
        except ElementNotFoundError:
            pass
        await asyncio.sleep(1)
    text = BeautifulSoup(code_ele.html, 'html.parser').get_text()
    code_text = text
    return code_text


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
