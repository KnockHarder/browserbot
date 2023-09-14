import os
import re
import sys
from typing import Optional

from PySide6.QtCore import Slot, Signal, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import QWidget, QTextEdit, QHBoxLayout, QVBoxLayout, QPushButton, QMessageBox, QComboBox, \
    QCompleter, QInputDialog, QApplication
from langchain import PromptTemplate
from langchain.prompts import load_prompt

import qt_utils as my_qt


class TemplateFileComboBox(QComboBox):
    template_selected = Signal(str)

    def __init__(self, parent: Optional[QWidget], dir_path):
        super().__init__(parent)
        self.dir_path = dir_path
        self.refresh()

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
        self.template_selected.emit(os.path.join(self.dir_path, selected_item))

    def activate_item(self, idx: int = -1, text: str = ''):
        if idx < 0 and text:
            idx = self.findText(text, Qt.MatchFlag.MatchExactly)
        if idx < 0:
            raise Exception('文件不存在')
        self.setCurrentIndex(idx)
        self.emit_item_selected(idx)

    def alloc_new_template_file_path(self, file_name: str) -> (str, str):
        if '.' not in file_name:
            file_name = file_name + '.json'
        else:
            [base, _] = file_name.split('.')[0:2]
            file_name = base + '.json'
        item_idx = self.findText(file_name, Qt.MatchFlag.MatchExactly)
        if item_idx >= 0:
            return '', os.path.join(self.dir_path, file_name)
        else:
            return file_name, os.path.join(self.dir_path, file_name)

    def refresh(self):
        self.clear()
        self.addItems(os.listdir(self.dir_path))


class PromptManagementPage(QWidget):
    current_template_file: str
    text_edit: QTextEdit
    templates_box: TemplateFileComboBox

    def __init__(self, parent: Optional[QWidget], templates_path):
        super().__init__(parent)
        layout = QHBoxLayout()
        layout.addLayout(self.template_edit_layout())
        layout.addLayout(self.operator_box_layout(templates_path))
        self.setLayout(layout)

    def template_edit_layout(self):
        # 左侧内容区
        layout = QVBoxLayout()
        self.text_edit = QTextEdit()
        layout.addWidget(self.text_edit)
        return layout

    def operator_box_layout(self, templates_path: str):
        layout = QVBoxLayout()

        self.templates_box = TemplateFileComboBox(self, templates_path)
        self.templates_box.template_selected.connect(self.set_curr_template)
        self.templates_box.activate_item(0)
        layout.addWidget(self.templates_box)

        for widget in [
            my_qt.simple_button('另存为', self.save_as_new),
            my_qt.simple_button('保存', self.save_template),
            my_qt.simple_button('重命名', self.rename_template_file)
        ]:
            layout.addWidget(widget)
        return layout

    @Slot(str)
    def set_curr_template(self, template_file_path: str):
        self.current_template_file = template_file_path
        self.text_edit.setText(load_prompt(self.current_template_file).template)

    @Slot()
    def save_template(self):
        template_file = self.current_template_file
        if template_file:
            self.save_as_new_file(template_file)

    def save_as_new_file(self, template_file):
        template = parse_template(self.text_edit.toPlainText())
        confirm_box = self.create_confirm_box(template, template_file)
        if confirm_box.exec_() == QMessageBox.StandardButton.Yes:
            template.save(template_file)

    def create_confirm_box(self, prompt: PromptTemplate, path: str) -> QMessageBox:
        confirm_dialog = QMessageBox(self)
        confirm_dialog.setIcon(QMessageBox.Icon.Question)
        confirm_dialog.setWindowTitle('保存提示词')
        confirm_dialog.setText(f'文件将被保存至: {path}')
        confirm_dialog.setInformativeText(f'变量: {prompt.input_variables}\n格式: {prompt.template_format}')
        confirm_dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        confirm_dialog.setDefaultButton(QMessageBox.StandardButton.No)
        return confirm_dialog

    @Slot()
    def save_as_new(self):
        file_name, confirmed = QInputDialog.getText(self, '新建模板文件', '文件名')
        if not confirmed:
            return
        item, file_path = self.templates_box.alloc_new_template_file_path(file_name)
        if not item:
            my_qt.popup_information_box(self, f'文件已存在: {file_path}')
            return
        self.save_as_new_file(file_path)
        self.templates_box.refresh()
        self.templates_box.activate_item(text=item)

    @Slot()
    def rename_template_file(self):
        curr_file_path = self.current_template_file
        if not curr_file_path:
            my_qt.popup_information_box(self, '请先选择Prompt')
            return
        prompt = load_prompt(curr_file_path)
        if prompt.template != self.text_edit.toPlainText():
            if not my_qt.popup_confirm_box(self, '是否revert当前template？'):
                return
            self.set_curr_template(curr_file_path)
        while True:
            name, confirmed = QInputDialog.getText(self, '重命名文件', '新的文件名')
            if not confirmed:
                return
            item, file_path = self.templates_box.alloc_new_template_file_path(name)
            if item:
                os.rename(curr_file_path, file_path)
                self.templates_box.refresh()
                return
            else:
                my_qt.popup_information_box(self, '文件已存在', QMessageBox.Icon.Critical)


def parse_template(template) -> PromptTemplate:
    variables = re.findall(r'(?<!\{)\{([a-zA-Z_]+)}', template)
    template_format = 'f-string'
    if not variables:
        variables = re.findall(r'\{\{([a-zA-Z_]+)}}', template)
        template_format = 'jinja2'
    return PromptTemplate(template=template, input_variables=variables, template_format=template_format)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    page = PromptManagementPage(None, os.path.expanduser('~/.my_py_datas/chatgpt/templates'))
    page.show()
    sys.exit(app.exec())
