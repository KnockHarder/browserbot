import time
from typing import Any

from DrissionPage import ChromiumPage
from DrissionPage.common import Keys
from bs4 import BeautifulSoup
from langchain import BasePromptTemplate


def find_and_switch_gpt_page(page):
    tab = page.find_tabs(url='https://chat.openai.com')
    page.to_tab(tab)


def gpt_page_new_chat(page, ques):
    page.ele('css:#__next nav > div.mb-1 > a').click.left()
    textarea = page.ele('#prompt-textarea')
    textarea.input(ques, clear=True)
    textarea.input(Keys.ENTER)


def delete_gpt_latest_chat(page):
    time.sleep(1)
    page.ele('css:#__next nav span:nth-child(1) button:nth-child(2)').click.left()
    page.ele('css:body div div button.btn.relative.btn-danger').click.left()


def get_gpt_code_answer(page):
    code_ele = page.ele('css:#__next main div.text-token-text-primary code')
    while code_ele.pseudo.after != 'none':
        time.sleep(0.1)
    code_text = BeautifulSoup(code_ele.html, 'html.parser').get_text()
    return code_text


def gen_code_question(page: ChromiumPage, prompt: BasePromptTemplate, delete_chat=True,
                      **kwargs: Any):
    find_and_switch_gpt_page(page)
    gpt_page_new_chat(page, prompt.format(**kwargs))
    code_ele = page.ele('css:#__next main div.text-token-text-primary code')
    while code_ele.pseudo.after != 'none':
        time.sleep(0.1)
    text = BeautifulSoup(code_ele.html, 'html.parser').get_text()
    code_text = text
    if delete_chat:
        delete_gpt_latest_chat(page)
    return code_text
