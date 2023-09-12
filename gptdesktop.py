import sys

from DrissionPage import ChromiumPage
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QPushButton, QHBoxLayout, QWidget

import gptweb
from gpt.codegen import CodeGeneratePage
from gpt.prompt import PromptManagementPage


class MyApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.browser_page = ChromiumPage()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('GPT助手')
        self.setGeometry(100, 100, 800, 800)

        layout = QVBoxLayout()
        layout.addLayout(self.init_buttons())
        layout.addLayout(self.init_main_side_bar())
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

    def init_main_side_bar(self):
        layout = QVBoxLayout()
        sidebar = QTabWidget(self)
        sidebar.addTab(CodeGeneratePage(), '代码生成')
        sidebar.addTab(PromptManagementPage(), '模板管理')
        layout.addWidget(sidebar)
        return layout

    def init_buttons(self):
        layout = QHBoxLayout()
        clear_button = QPushButton('清空历史')
        clear_button.clicked.connect(self.clear_chats)
        clear_button.setStyleSheet('background-color: red; color: white')

        new_chat_button = QPushButton('New Chat')
        new_chat_button.clicked.connect(self.new_chat)
        layout.addWidget(new_chat_button)
        layout.addWidget(clear_button)
        return layout

    @Slot()
    def clear_chats(self):
        gptweb.clear_chat_history(self.browser_page)

    @Slot()
    def new_chat(self):
        gptweb.start_new_chat(self.browser_page)


def main():
    app = QApplication(sys.argv)
    window = MyApp()
    window.move(window.x(), app.primaryScreen().size().height() / 2)

    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
