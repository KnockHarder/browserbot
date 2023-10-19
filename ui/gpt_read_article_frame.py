from typing import Optional, Callable

from PySide6.QtCore import Signal, Slot, Qt
from PySide6.QtGui import QPicture
from PySide6.QtWidgets import QFrame, QWidget, QListWidgetItem

import config as my_config
import gpt.reader as gpt_reader
from gpt.reader import Article
from browser import Browser, TabInfo as BrowserTab
from mywidgets import MarkdownItemDelegate


class PageArticleReader:
    article: Article

    def __init__(self, tab: BrowserTab, page_read_func: Callable[[Browser], Article]):
        self.tab = tab
        self.article_content_func = page_read_func
        self.initialized = False

    def get_article(self, browser: Browser) -> Article:
        if self.initialized:
            return self.article
        self.article = self.article_content_func(browser)


def markdown_link(reader: PageArticleReader):
    tab = reader.tab
    return f'[{tab.title}]({tab.url})'


def create_page_article_reader(tab) -> Optional[PageArticleReader]:
    if tab.url.startswith('https://mp.weixin.qq.com/s/'):
        return PageArticleReader(tab, gpt_reader.read_weixin_article)
    if (tab.url.startswith('https://www.infoq.cn/article')
            or tab.url.startswith('https://www.infoq.cn/news/')):
        return PageArticleReader(tab, gpt_reader.read_info_q_article)
    return None


class GptReadArticleFrame(QFrame):
    contentImageUpdate = Signal(QPicture)
    READER_DATA_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        from ui.gpt_read_article_frame_uic import Ui_gptReadArticleFrame
        self.ui = Ui_gptReadArticleFrame()
        self.ui.setupUi(self)
        self.ui.articleListWidget.setItemDelegate(MarkdownItemDelegate())

        self.browser = my_config.get_browser()
        self.update_article_list()

    @Slot()
    def update_article_list(self):
        browser = self.browser
        readers = list(filter(lambda x: x, map(create_page_article_reader, browser.tabs)))

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
