import os
import subprocess
import sys
from typing import Optional

from DrissionPage import ChromiumPage
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QWidget, QTextEdit, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, \
    QGridLayout, QLayout, QLineEdit, QApplication
from jinja2 import TemplateError
from langchain import BasePromptTemplate
from langchain.prompts import load_prompt

import gpt.prompt as my_prompt
from gpt import gpt_util
from gpt.prompt import TemplateFileComboBox
import qt_utils as my_qt


def clear_layout(layout: QLayout):
    for i in reversed(range(layout.count())):
        item = layout.itemAt(i)
        if item and item.widget():
            item.widget().deleteLater()


def remove_grid_layout_row(layout: QGridLayout, row: int, remove_widget: bool):
    for col in range(layout.columnCount()):
        position_layout = layout.itemAtPosition(row, col)
        if position_layout:
            if remove_widget:
                position_layout.widget().deleteLater()
            layout.removeItem(position_layout)


class CodeGeneratePage(QWidget):
    curr_prompt: BasePromptTemplate
    template_editor: QTextEdit
    answer_editor: QTextEdit
    variables_layout: QGridLayout
    variable_label_widget_dict: dict[str, (QLabel, QWidget)] = dict()

    def __init__(self, parent: Optional[QWidget], browser_agent: ChromiumPage, templates_path):
        super().__init__(parent)
        self.chromium_page = browser_agent

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        main_layout.addLayout(self.question_area())
        layout = QHBoxLayout()
        layout.addLayout(self.answer_layout())
        layout.addLayout(self.operator_layout(templates_path))
        main_layout.addLayout(layout)

    def question_area(self) -> QLayout:
        layout1 = QVBoxLayout()
        self.template_editor = QTextEdit(self)
        self.template_editor.textChanged.connect(self.update_variables_layout)
        layout1.addWidget(QLabel('模板内容', self))
        layout1.addWidget(self.template_editor)

        layout2 = QVBoxLayout()
        layout2.addWidget(QLabel('模板变量'))
        self.variables_layout = QGridLayout()
        layout2.addLayout(self.variables_layout)

        main_layout = QHBoxLayout()
        main_layout.addLayout(layout1)
        main_layout.addLayout(layout2)
        return main_layout

    def answer_layout(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel('回答代码'))
        self.answer_editor = QTextEdit(self)
        layout.addWidget(self.answer_editor)
        return layout

    def operator_layout(self, templates_path: str):
        search_box = TemplateFileComboBox(self, templates_path)
        search_box.template_selected.connect(self.template_switch)
        search_box.setCurrentIndex(0)
        search_box.emit_item_selected(0)

        layout = QVBoxLayout()
        layout.addWidget(search_box)
        for widget in [
            my_qt.simple_button('刷新模板', search_box.refresh),
            my_qt.simple_button('生成代码', self.submit_question),
            my_qt.simple_button('复制回答', self.copy_answer)
        ]:
            layout.addWidget(widget)
        return layout

    @Slot(str)
    def template_switch(self, template_file: str):
        self.curr_prompt = load_prompt(template_file)
        self.template_editor.setText(self.curr_prompt.template)

    @Slot()
    def copy_answer(self):
        subprocess.Popen('pbcopy', shell=True, stdin=subprocess.PIPE) \
            .communicate(input=self.answer_editor.toPlainText())

    @Slot(str)
    def update_variables_layout(self):
        template = self.template_editor.toPlainText()
        if not self.curr_prompt or self.curr_prompt.template != template:
            try:
                self.curr_prompt = my_prompt.parse_template(template)
            except (ValueError, TemplateError):
                print("Invalid template")
                return
        all_variables = self.curr_prompt.input_variables
        variables_layout = self.variables_layout
        variable_widget_dict = self.variable_label_widget_dict
        for variable in set(variable_widget_dict.keys()):
            label, _ = variable_widget_dict.get(variable)
            row = variables_layout.getItemPosition(variables_layout.indexOf(label))[0]
            if variable not in all_variables:
                del variable_widget_dict[variable]
                remove_grid_layout_row(variables_layout, row, True)
            else:
                remove_grid_layout_row(variables_layout, row, False)
        for idx, variable in enumerate(all_variables):
            if variable in variable_widget_dict.keys():
                (label, widget) = variable_widget_dict.get(variable)
            else:
                label = QLabel(variable, self)
                widget = QTextEdit(self) if idx == len(all_variables) - 1 \
                    else QLineEdit(self)
                variable_widget_dict[variable] = (label, widget)
            variables_layout.addWidget(label, idx, 0)
            variables_layout.addWidget(widget, idx, 1)

        variables_layout.update()

    def submit_question(self):
        param_map = dict()
        for variable, (_, widget) in self.variable_label_widget_dict.items():
            content = widget.text() if isinstance(widget, QLineEdit) \
                else widget.toPlainText()
            param_map[variable] = content
        answer = gpt_util.gen_code_question(self.chromium_page, self.curr_prompt, **param_map)
        self.answer_editor.setText(answer)


if __name__ == '__main__':
    def main():
        app = QApplication()
        page = CodeGeneratePage(None, ChromiumPage(), os.path.expanduser('~/.my_py_datas/chatgpt/templates'))
        screen_size = app.primaryScreen().size()
        page.setGeometry(350, screen_size.height() / 2, 1000, 800)
        page.show()
        sys.exit(app.exec())


    main()
