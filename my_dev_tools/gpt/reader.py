import asyncio

from bs4 import BeautifulSoup

from ..browser_dom import PageNode
from ..browser_page import BrowserPage

ARTICLE_READ_TIMEOUT = 5


class Article:
    def __init__(self, title: str, plain_content: str, url: str = None):
        self.name = title.strip()
        self.content = plain_content
        self.url = url


async def _get_paragraphs_text(node: PageNode, tag_name: str) -> str:
    root_tag = BeautifulSoup(await node.outer_html, 'html.parser')
    paragraphs = root_tag.find_all(tag_name)
    paragraphs = [x.get_text() for x in paragraphs if not x.find_all(tag_name)]
    return '\n'.join(paragraphs)


async def extract_info_q_article(page: BrowserPage):
    title_node = await page.require_single_node_by_xpath('(//h1)[1]', ARTICLE_READ_TIMEOUT)
    content_node = await page.require_single_node_by_xpath(
        '//*[@class="content-main"]//*[@class="article-preview"][1]', ARTICLE_READ_TIMEOUT)
    return Article(await title_node.text_content,
                   await _get_paragraphs_text(content_node, 'p'))


async def extract_weixin_article(page: BrowserPage) -> Article:
    content_ele = await page.require_single_node_by_xpath('//*[@id="js_content"][1]', ARTICLE_READ_TIMEOUT)
    section = await _get_paragraphs_text(content_ele, 'section')
    p = await _get_paragraphs_text(content_ele, 'p')
    title_node = await page.require_single_node_by_xpath('(//h1)[1]', ARTICLE_READ_TIMEOUT)
    return Article(await title_node.text_content, p if len(p) > len(section) else section)


def main():
    from .chat_gpt_page import ChatGptPage
    page = ChatGptPage()
    asyncio.run(page.read_articles())
