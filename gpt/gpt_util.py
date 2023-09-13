import time
from typing import Any

from DrissionPage import ChromiumPage
from DrissionPage.common import Keys
from bs4 import BeautifulSoup
from langchain import BasePromptTemplate

import chromium_utils as my_chromium_utils


def find_and_switch_gpt_page(page):
    tab = page.find_tabs(url='https://chat.openai.com')
    page.to_tab(tab)


def start_new_chat(page):
    find_and_switch_gpt_page(page)
    page.ele('tag:a@text()=New chat').click()


def ask_as_new_chat(page, ques):
    start_new_chat(page)
    textarea = page.ele('#prompt-textarea')
    textarea.input(ques, clear=True)
    textarea.input(Keys.ENTER)


def get_gpt_code_answer(page: ChromiumPage):
    code_ele = page.ele('css:#__next main div.text-token-text-primary code')
    while code_ele.pseudo.after != 'none':
        time.sleep(0.1)
    code_text = BeautifulSoup(code_ele.html, 'html.parser').get_text()
    return code_text


def gen_code_question(page: ChromiumPage, prompt: BasePromptTemplate, **kwargs: Any):
    find_and_switch_gpt_page(page)
    ask_as_new_chat(page, prompt.format(**kwargs))
    code_ele = page.ele('css:#__next main div.text-token-text-primary code')
    while code_ele.pseudo.after != 'none':
        time.sleep(0.1)
    text = BeautifulSoup(code_ele.html, 'html.parser').get_text()
    code_text = text
    return code_text


def clear_chat_history(page: ChromiumPage):
    find_and_switch_gpt_page(page)
    chat_list = my_chromium_utils.wait_elements(
        lambda: page.ele('tag:h2@text()=Chat history').next('tag:nav').eles('tag:li'), 5)
    if not chat_list:
        raise Exception('No chat')
    for chat in chat_list:
        chat.ele('tag:a').click()
        chat_buttons = my_chromium_utils.wait_elements(lambda: chat.eles('tag:button'))
        chat_buttons[1].click()
        page.ele('tag:button@text()=Delete').click()
