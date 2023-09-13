import os.path
import sys
from typing import Optional

from DrissionPage import ChromiumPage
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QApplication, QTabWidget, QVBoxLayout, QPushButton, QHBoxLayout, QWidget

from gpt import gpt_util
from gpt.codegen import CodeGeneratePage
from gpt.prompt import PromptManagementPage


class GptHelperWidget(QWidget):
    def __init__(self, parent: Optional[QWidget], browser_agent, templates_path):
        super().__init__(parent)
        self.browser_agent = browser_agent
        self.init_ui(templates_path)

    def init_ui(self, templates_path):
        layout = QVBoxLayout()
        layout.addLayout(self.init_buttons())
        layout.addLayout(self.init_main_side_bar(templates_path))
        self.setLayout(layout)

    def init_main_side_bar(self, templates_path):
        layout = QVBoxLayout()
        sidebar = QTabWidget(self)
        sidebar.addTab(CodeGeneratePage(self, self.browser_agent, templates_path), '代码生成')
        sidebar.addTab(PromptManagementPage(self, templates_path), '模板管理')
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
        gpt_util.clear_chat_history(self.browser_agent)

    @Slot()
    def new_chat(self):
        gpt_util.start_new_chat(self.browser_agent)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    widget = GptHelperWidget(ChromiumPage(), os.path.expanduser('~/.my_py_datas/chatgpt/templates'))
    widget.setWindowTitle('GPT助手')
    widget.setGeometry(100, 100, 800, 800)
    widget.move(350, 1200)
    widget.show()
    sys.exit(app.exec_())
