import os.path
from typing import Callable

from bs4 import BeautifulSoup
from langchain import prompts
from transformers import AutoTokenizer

import gpt.gpt_util as my_gpt
from browser import Browser, PageElement


class Article:
    def __init__(self, title: str, plain_content: str, url: str = None):
        self.name = title
        self.content = plain_content
        self.url = url


def get_paragraphs_text(ele: PageElement, tag_name: str) -> str:
    root_tag = BeautifulSoup(ele.html, 'html.parser')
    paragraphs = root_tag.find_all(tag_name)
    paragraphs = [x.get_text() for x in paragraphs if not x.find_all(tag_name)]
    return '\n'.join(paragraphs)


def token_size(text: str):
    if not text:
        return 0
    tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
    tokens = tokenizer.tokenize(text)
    return len(tokens)


def summarize_article(browser: Browser, article: Article):
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
    my_gpt.ask_as_new_chat_and_wait(browser, instruction_prompt.format(article_name=article.name))
    text_len_limit = int(len(article.content) / content_token * token_limit)
    text = ''
    for line in article.content.split('\n'):
        if len(line) > text_len_limit:
            raise Exception('To long paragraph', f'{line[:20]}...{line[-20:]}')
        if len(text) + len(line) > 4096:
            my_gpt.continue_ask_and_wait(browser, part_content_prompt.format(content=text))
            text = line
        else:
            text = '\n'.join([text, line])
    if text:
        my_gpt.continue_ask_and_wait(browser,
                                     end_content_prompt.format(
                                         caption=article.name, url=article.url, content=text))


def read_info_q_article(browser: Browser) -> Article:
    return Article(browser.search_elements('tag:h1')[0].text,
                   get_paragraphs_text(browser.search_elements('.content-main')('.article-preview')[0], 'p'))


def read_weixin_article(browser: Browser) -> Article:
    content_ele = browser.search_elements('#js_content')[0]
    section = get_paragraphs_text(content_ele, 'section')
    p = get_paragraphs_text(content_ele, 'p')
    return Article(browser.search_elements('tag:h1')[0].text,
                   p if len(p) > len(section) else section)


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
        article.url = tab.url
        if not article.name or not article.content:
            print('No title or paragraph content', tab.url)
            continue
        summarize_article(browser, article)
        tab.close()


def main():
    browser = Browser()
    read_all_page_articles(browser, 'https://mp.weixin.qq.com/s/', read_weixin_article)
    read_all_page_articles(browser, 'https://mp.weixin.qq.com/s?', read_weixin_article)
    read_all_page_articles(browser, 'https://www.infoq.cn/article', read_info_q_article)
    read_all_page_articles(browser, 'https://www.infoq.cn/news/', read_info_q_article)


if __name__ == '__main__':
    main()
