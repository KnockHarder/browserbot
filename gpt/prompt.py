import os
import re

from PySide6.QtCore import Slot, Signal, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import QWidget, QTextEdit, QHBoxLayout, QVBoxLayout, QPushButton, QMessageBox, QComboBox, \
    QCompleter
from langchain import BasePromptTemplate, PromptTemplate
from langchain.prompts import load_prompt


class PromptManagementPage(QWidget):
    current_template_file: str
    curr_prompt: BasePromptTemplate
    text_edit: QTextEdit

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout()
        layout.addLayout(self.template_edit_layout())
        layout.addLayout(self.operator_box_layout())
        self.setLayout(layout)

    def template_edit_layout(self):
        # 左侧内容区
        layout = QVBoxLayout()
        self.text_edit = QTextEdit()
        layout.addWidget(self.text_edit)
        return layout

    def operator_box_layout(self):
        layout = QVBoxLayout()

        search_box = TemplateFileComboBox()
        search_box.template_selected.connect(self.template_switch)
        search_box.setCurrentIndex(0)
        search_box.emit_item_selected(0)

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
            template = parse_template(self.text_edit.toPlainText())
            confirm_box = self.create_confirm_box(template)
            self.move_to_center(confirm_box)
            if confirm_box.exec_() == QMessageBox.StandardButton.Yes:
                template.save(template_file)

    def create_confirm_box(self, prompt: PromptTemplate) -> QMessageBox:
        confirm_dialog = QMessageBox(self)
        confirm_dialog.setIcon(QMessageBox.Icon.Question)
        confirm_dialog.setWindowTitle('保存提示词')
        confirm_dialog.setText(f'文件将被保存至: {self.current_template_file}')
        confirm_dialog.setInformativeText(f'变量: {prompt.input_variables}\n格式: {prompt.template_format}')
        confirm_dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        confirm_dialog.setDefaultButton(QMessageBox.StandardButton.No)
        return confirm_dialog

    def move_to_center(self, widget: QWidget):
        widget.move(x=self.pos().x() + widget.width() / 2, y=self.pos().y() + widget.height() / 2)


def parse_template(template) -> PromptTemplate:
    variables = re.findall(r'(?<!\{)\{([a-zA-Z_]+)}', template)
    template_format = 'f-string'
    if not variables:
        variables = re.findall(r'\{\{([a-zA-Z_]+)}}', template)
        template_format = 'jinja2'
    return PromptTemplate(template=template, input_variables=variables, template_format=template_format)


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
