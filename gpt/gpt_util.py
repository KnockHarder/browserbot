import time
from typing import Any

from DrissionPage import ChromiumPage
from DrissionPage.common import Keys
from bs4 import BeautifulSoup
from langchain import BasePromptTemplate

import chromium_utils as my_chromium_utils


def _find_and_switch_gpt_page(page):
    tab = page.find_tabs(url='https://chat.openai.com')
    page.to_tab(tab)


def start_new_chat(page):
    _find_and_switch_gpt_page(page)
    page.ele('tag:a@text()=New chat').click()


def _ask_as_new_chat(page, ques):
    start_new_chat(page)
    _continue_ask(page, ques)


def _continue_ask(page, ques):
    textarea = page.ele('#prompt-textarea')
    textarea.input(ques, clear=True)
    textarea.input(Keys.ENTER)


def gen_code_question(page: ChromiumPage, prompt: BasePromptTemplate, **kwargs: Any):
    _find_and_switch_gpt_page(page)
    _ask_as_new_chat(page, prompt.format(**kwargs))
    code_ele = page.ele('css:#__next main div.text-token-text-primary code')
    while code_ele.pseudo.after != 'none':
        time.sleep(0.1)
    text = BeautifulSoup(code_ele.html, 'html.parser').get_text()
    code_text = text
    return code_text


def clear_chat_history(page: ChromiumPage):
    _find_and_switch_gpt_page(page)
    chat_list = my_chromium_utils.wait_elements(
        lambda: page.ele('tag:h2@text()=Chat history').next('tag:nav').eles('tag:li'), 5)
    if not chat_list:
        raise Exception('No chat')
    for chat in chat_list:
        chat.ele('tag:a').click()
        chat_buttons = my_chromium_utils.wait_elements(lambda: chat.eles('tag:button'))
        chat_buttons[1].click()
        page.ele('tag:button@text()=Delete').click()
        time.sleep(0.2)


def ask_as_new_chat_and_wait(browser: ChromiumPage, question: str):
    _ask_as_new_chat(browser, question)
    _wait_answer_done(browser)


def continue_ask_and_wait(browser: ChromiumPage, question: str):
    message_size = len(browser.eles('css:main div.text-token-text-primary'))
    _continue_ask(browser, question)
    _wait_answer_done(browser, message_size)


def _wait_answer_done(browser, before_ask_size=0):
    messages = browser.eles('css:main div.text-token-text-primary')
    while len(messages) < before_ask_size + 2:
        time.sleep(0.1)
    answer = browser.eles('css:main div.text-token-text-primary')[-1]
    while not answer.text \
            or not answer.eles('tag:p') \
            or any(x.pseudo.after != 'none' for x in answer.eles('tag:p')) \
            or any(x.pseudo.after != 'none' for x in answer.eles('tag:li')):
        answer = browser.eles('css:main div.text-token-text-primary')[-1]
        time.sleep(0.1)


if __name__ == '__main__':
    ask_as_new_chat_and_wait(ChromiumPage(), '最近有什么科技新闻吗？')
