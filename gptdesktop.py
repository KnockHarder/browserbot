import os
import re
import sys

from PySide6.QtCore import Signal, Slot, Qt, QSortFilterProxyModel
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QTextEdit, QVBoxLayout, QHBoxLayout, QWidget, \
    QPushButton, QComboBox, QCompleter, QMessageBox
from langchain import BasePromptTemplate, PromptTemplate
from langchain.prompts import load_prompt


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


class PromptManagementPage(QWidget):
    current_template_file: str
    curr_prompt: BasePromptTemplate
    text_edit: QTextEdit

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout()
        layout.addLayout(self.text_edit_widget())
        layout.addLayout(self.operator_box_widget())
        self.setLayout(layout)

    def text_edit_widget(self):
        # 左侧内容区
        layout = QVBoxLayout()
        self.text_edit = QTextEdit()
        layout.addWidget(self.text_edit)
        return layout

    def operator_box_widget(self):
        layout = QVBoxLayout()

        search_box = TemplateFileComboBox()
        search_box.template_selected.connect(self.template_switch)

        save_button = QPushButton('保存')
        save_button.clicked.connect(self.save_template)

        layout.addWidget(search_box)
        layout.addWidget(save_button)
        return layout

    @Slot(str)
    def template_switch(self, template_file_path: str):
        self.current_template_file = template_file_path
        self.curr_prompt = load_prompt(self.current_template_file)
        self.text_edit.setText(self.curr_prompt.template)

    @Slot()
    def save_template(self):
        template_file = self.current_template_file
        if template_file:
            template = self.parse_template(self.text_edit.toPlainText())
            confirm_box = self.create_confirm_box(template)
            if confirm_box.exec_() == QMessageBox.StandardButton.Yes:
                template.save(template_file)

    def parse_template(self, template) -> PromptTemplate:
        variables = re.findall(r'(?<!\{)\{([a-zA-Z_]+)}', template)
        template_format = 'f-string'
        if not variables:
            variables = re.findall(r'\{\{([a-zA-Z_]+)}}', template)
            template_format = 'jinja2'
        return PromptTemplate(template=template, input_variables=variables, template_format=template_format)

    def create_confirm_box(self, prompt: PromptTemplate) -> QMessageBox:
        confirm_dialog = QMessageBox(self)
        confirm_dialog.setIcon(QMessageBox.Icon.Question)
        confirm_dialog.setWindowTitle('保存提示词')
        confirm_dialog.setText(f'文件将被保存至: {self.current_template_file}')
        confirm_dialog.setInformativeText(f'变量: {prompt.input_variables}\n格式: {prompt.template_format}')
        confirm_dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        confirm_dialog.setDefaultButton(QMessageBox.StandardButton.No)
        return confirm_dialog


class TemplateFileComboBox(QComboBox):
    base_dir = './templates/'
    template_selected = Signal(str)

    def __init__(self):
        super().__init__()
        all_templates = os.listdir(self.base_dir)
        self.addItems(all_templates)

        self.setEditable(True)
        self.filter_mode = QSortFilterProxyModel(self)
        self.filter_mode.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.filter_mode.setSourceModel(self.model())
        self.setCompleter(QCompleter(self.filter_mode, self))
        self.completer().setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)

        self.lineEdit().textEdited.connect(self.set_filter_text)
        self.activated.connect(self.emit_item_selected)

    @Slot(str)
    def set_filter_text(self, chars: str):
        if not chars:
            return
        pattern = '.*' + r'.*'.join(list(chars.strip())) + '.*'
        self.filter_mode.setFilterRegularExpression(pattern)

    @Slot(str)
    def select_complete(self, text: str):
        if not text:
            return
        index = self.findText(text)
        self.setCurrentIndex(index)

    @Slot(int)
    def emit_item_selected(self, index: int):
        selected_item = self.itemText(index)
        self.template_selected.emit(self.base_dir + selected_item)


def main():
    app = QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
