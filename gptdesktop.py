import sys

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QTextEdit, QVBoxLayout, QHBoxLayout, QWidget, \
    QPushButton
from langchain.prompts import load_prompt

from gpt.prompt import PromptManagementPage, TemplateFileComboBox


class MyApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('GPT助手')
        self.setGeometry(100, 100, 800, 600)

        side_bar = self.create_main_side_bar()
        self.setCentralWidget(side_bar)

    def create_main_side_bar(self):
        # 创建左侧边栏
        sidebar = QTabWidget(self)
        sidebar.addTab(CodeGeneratePage(), '代码生成')
        sidebar.addTab(PromptManagementPage(), '模板管理')
        return sidebar


class CodeGeneratePage(QWidget):
    current_template: str
    question_editor: QTextEdit
    answer_editor: QTextEdit

    def __init__(self):
        super().__init__()

        layout = QHBoxLayout()
        layout.addLayout(self.gpt_content_area())
        layout.addLayout(self.operator_area_widget())
        self.setLayout(layout)

    def gpt_content_area(self):
        tabs = QTabWidget()
        self.question_editor = QTextEdit()
        tabs.addTab(self.question_editor, '提问')
        self.answer_editor = QTextEdit()
        tabs.addTab(self.answer_editor, '回答')
        tabs.setTabPosition(QTabWidget.TabPosition.West)
        layout = QVBoxLayout()
        layout.addWidget(tabs)
        return layout

    def operator_area_widget(self):
        search_box = TemplateFileComboBox()
        search_box.template_selected.connect(self.template_switch)

        copy_button = QPushButton('复制')
        paste_button = QPushButton('粘贴')
        layout = QVBoxLayout()
        layout.addWidget(search_box)
        layout.addWidget(copy_button)
        layout.addWidget(paste_button)
        return layout

    @Slot(str)
    def template_switch(self, template: str):
        self.current_template = template
        prompt = load_prompt(self.current_template)
        self.question_editor.setText(prompt.template)


def main():
    app = QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
