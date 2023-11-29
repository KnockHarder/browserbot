from typing import Optional, Callable, Coroutine

from PySide6.QtCore import Signal, Slot, Qt
from PySide6.QtGui import QPicture
from PySide6.QtWidgets import QFrame, QWidget, QListWidgetItem

from ..browser import get_browser
from ..browser_page import BrowserPage
from ..gpt import Article
from ..gpt import reader as gpt_reader
from ..widgets import MarkdownItemDelegate


class PageArticleReader:
    article: Article

    def __init__(self, page: BrowserPage, page_read_func: Callable[[BrowserPage], Coroutine[Article]]):
        self.page = page
        self.article_content_func = page_read_func
        self.initialized = False

    async def get_article(self) -> Article:
        if self.initialized:
            return self.article
        self.article = await self.article_content_func(self.page)


def markdown_link(reader: PageArticleReader):
    page = reader.page
    return f'[{page.title}]({page.url})'


def create_page_article_reader(page: BrowserPage) -> Optional[PageArticleReader]:
    if page.url.startswith('https://mp.weixin.qq.com/s/'):
        return PageArticleReader(page, gpt_reader.read_weixin_article)
    if (page.url.startswith('https://www.infoq.cn/article')
            or page.url.startswith('https://www.infoq.cn/news/')):
        return PageArticleReader(page, gpt_reader.read_info_q_article)
    return None


class GptReadArticleFrame(QFrame):
    contentImageUpdate = Signal(QPicture)
    READER_DATA_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        from ..ui.gpt_read_article_frame_uic import Ui_gptReadArticleFrame
        self.ui = Ui_gptReadArticleFrame()
        self.ui.setupUi(self)
        self.ui.articleListWidget.setItemDelegate(MarkdownItemDelegate())

        self.browser = get_browser()
        self.update_article_list()

    @Slot()
    def update_article_list(self):
        browser = self.browser
        readers = list(filter(lambda x: x, map(create_page_article_reader, browser.pages)))

        list_widget = self.ui.articleListWidget
        list_widget.clear()
        for rd in readers:
            item = QListWidgetItem(markdown_link(rd))
            item.setData(self.READER_DATA_ROLE, rd)
            list_widget.addItem(item)

    def read_article_from_url(self):
        ...

    def read_next_article(self):
        ...


if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication


    def main():
        app = QApplication()
        frame = GptReadArticleFrame()
        frame.show()
        sys.exit(app.exec())


    main()
