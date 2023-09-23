import os.path
import time
from typing import Callable

from DrissionPage import ChromiumPage
from DrissionPage.chromium_element import ChromiumElement
from bs4 import BeautifulSoup
from langchain import prompts
from transformers import AutoTokenizer

import chromium_utils as my_ch
import gpt.gpt_util as my_gpt


def get_paragraphs_text(ele: ChromiumElement, tag_name: str):
    soup = BeautifulSoup(ele.html, 'html.parser')
    paragraphs = soup.find_all(tag_name)
    text = ''
    for p in paragraphs:
        text = text + p.get_text() + '\n'
    return text


def token_size(text):
    if not text:
        return 0
    tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
    tokens = tokenizer.tokenize(text)
    return len(tokens)


def summarize_article(browser, title, paragraphs_text):
    content_token = token_size(paragraphs_text)
    if not content_token:
        print(f"{title} has empty paragraph text")
        return
    template_dir = os.path.expanduser('~/.my_py_datas/chatgpt/templates')
    instruction_prompt = prompts.load_prompt(os.path.join(template_dir, '文章阅读_指令.json'))
    part_content_prompt = prompts.load_prompt(os.path.join(template_dir, '文章阅读_partContent.json'))
    end_content_prompt = prompts.load_prompt(os.path.join(template_dir, '文章阅读_endContent.json'))

    prompt_token_size = max([token_size(part_content_prompt.format(content='')),
                             token_size(end_content_prompt.format(content=''))])
    token_limit = 4096 - prompt_token_size
    my_gpt.ask_as_new_chat_and_wait(browser, instruction_prompt.format(article_name=title))
    text_len_limit = int(len(paragraphs_text) / content_token * token_limit)
    text = ''
    for line in paragraphs_text.split('\n'):
        if len(line) > text_len_limit:
            raise Exception('To long paragraph')
        if len(text) + len(line) > 4096:
            my_gpt.continue_ask_and_wait(browser, part_content_prompt.format(content=text))
            text = line
        else:
            text = '\n'.join([text, line])
    if text:
        my_gpt.continue_ask_and_wait(browser, end_content_prompt.format(content=text))


def read_info_q_articles(browser: ChromiumPage):
    def get_article_content(bws: ChromiumPage):
        return (bws.ele('tag:h1').text,
                get_paragraphs_text(bws.ele('.content-main')('.article-preview'), 'p'))

    read_all_page_articles(browser, 'https://www.infoq.cn/article', get_article_content)
    read_all_page_articles(browser, 'https://www.infoq.cn/news/', get_article_content)


def read_wx_articles(browser: ChromiumPage):
    def get_wx_paragraphs_text(page: ChromiumPage):
        section = get_paragraphs_text(page.ele('#js_content'), 'section')
        p = text = get_paragraphs_text(page.ele('#js_content'), 'p')
        return p if len(p) > len(section) else section

    read_all_page_articles(browser, 'https://mp.weixin.qq.com/s/',
                           lambda page: (page.ele('tag:h1').text, get_wx_paragraphs_text(page)))


def read_all_page_articles(browser, article_url_prefix,
                           article_content_func: Callable[[ChromiumPage], tuple[str, str]]):
    tabs = my_ch.find_all_tab_id(browser, article_url_prefix)
    if not tabs:
        print('Cannot find any article tab', article_url_prefix)
        return
    for idx, tab in enumerate(tabs):
        browser.to_tab(tab)
        title, paragraphs = article_content_func(browser)
        if not title or not paragraphs:
            print('No title or paragraph content', browser.url)
            continue
        summarize_article(browser, title, paragraphs)
        if idx + 1 < len(tabs):
            while tab in my_ch.find_all_tab_id(browser, article_url_prefix):
                time.sleep(1)


def open_info_q_mail_urls(browser: ChromiumPage):
    urls = {x.attr('href') for x in browser.eles('tag:a@href:https://etrack01')}
    for u in urls:
        browser.new_tab(url=u, switch_to=False)


if __name__ == '__main__':
    def print_ele(ele):
        if isinstance(ele, list):
            print(len(ele))
            _ = [print(x) for x in ele]
        else:
            print(ele)


    read_wx_articles(ChromiumPage())
