import os.path
import time
from typing import Callable

from DrissionPage.chromium_element import ChromiumElement
from bs4 import BeautifulSoup
from langchain import prompts
from transformers import AutoTokenizer

import gpt.gpt_util as my_gpt
from browser import Browser


class Article:
    def __init__(self, title: str, plain_content: str):
        self.name = title
        self.content = plain_content


def get_paragraphs_text(ele: ChromiumElement, tag_name: str) -> str:
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


def summarize_article(browser, article: Article):
    content_token = token_size(article.content)
    if not content_token:
        print(f"{article.name} has empty paragraph text")
        return
    template_dir = os.path.expanduser('~/.my_py_datas/chatgpt/templates')
    instruction_prompt = prompts.load_prompt(os.path.join(template_dir, '文章阅读_指令.json'))
    part_content_prompt = prompts.load_prompt(os.path.join(template_dir, '文章阅读_partContent.json'))
    end_content_prompt = prompts.load_prompt(os.path.join(template_dir, '文章阅读_endContent.json'))

    prompt_token_size = max([token_size(part_content_prompt.format(content='')),
                             token_size(end_content_prompt.format(content=''))])
    token_limit = 4096 - prompt_token_size
    my_gpt.ask_as_new_chat_and_wait(browser, instruction_prompt.format(article_name=article.name))
    text_len_limit = int(len(article.content) / content_token * token_limit)
    text = ''
    for line in article.content.split('\n'):
        if len(line) > text_len_limit:
            raise Exception('To long paragraph')
        if len(text) + len(line) > 4096:
            my_gpt.continue_ask_and_wait(browser, part_content_prompt.format(content=text))
            text = line
        else:
            text = '\n'.join([text, line])
    if text:
        my_gpt.continue_ask_and_wait(browser, end_content_prompt.format(content=text))


def read_info_q_article(browser: Browser) -> Article:
    page = browser.page
    return Article(page.ele('tag:h1').text,
                   get_paragraphs_text(page.ele('.content-main')('.article-preview'), 'p'))


def read_weixin_article(browser: Browser) -> Article:
    page = browser.page
    section = get_paragraphs_text(page.ele('#js_content'), 'section')
    p = get_paragraphs_text(page.ele('#js_content'), 'p')
    return Article(page.ele('tag:h1').text,
                   p if len(p) > len(section) else section)


def read_info_q_articles(browser: Browser):
    read_all_page_articles(browser, 'https://www.infoq.cn/article', read_info_q_article)
    read_all_page_articles(browser, 'https://www.infoq.cn/news/', read_info_q_article)


def read_wx_articles(browser: Browser):
    read_all_page_articles(browser.page, 'https://mp.weixin.qq.com/s/',
                           lambda page: read_weixin_article(page))


def read_all_page_articles(browser: Browser, article_url_prefix,
                           article_content_func: Callable[[Browser], Article]):
    tab_list = browser.all_tab_with_prefix(article_url_prefix)
    if not tab_list:
        print('Cannot find any article tab', article_url_prefix)
        return
    while tab_list:
        tab = tab_list.pop()
        browser.to_tab(tab)
        article = article_content_func(browser)
        if not article.name or not article.content:
            print('No title or paragraph content', tab.url)
            continue
        summarize_article(browser, article)
        if tab_list:
            while browser.is_tab_alive(tab):
                time.sleep(1)


def open_info_q_mail_urls(browser: Browser):
    urls = {x.attr('href') for x in browser.page.eles('tag:a@href:https://etrack01')}
    for u in urls:
        browser.page.new_tab(url=u, switch_to=False)


if __name__ == '__main__':
    def print_ele(ele):
        if isinstance(ele, list):
            print(len(ele))
            _ = [print(x) for x in ele]
        else:
            print(ele)


    read_wx_articles(Browser())
