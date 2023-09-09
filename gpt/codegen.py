import subprocess

from DrissionPage import ChromiumPage
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QWidget, QTextEdit, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, \
    QGridLayout, QLayout, QLineEdit
from langchain import BasePromptTemplate
from langchain.prompts import load_prompt

from gpt.prompt import TemplateFileComboBox, parse_template
from gptweb import gen_code_question


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

    def __init__(self):
        super().__init__()
        self.chromium_page = ChromiumPage()

        layout = QHBoxLayout()
        layout.addLayout(self.gpt_content_area())
        layout.addLayout(self.operator_area_widget())
        self.setLayout(layout)

    def gpt_content_area(self):
        layout = QVBoxLayout()
        layout.addLayout(self.question_area())
        layout.addLayout(self.answer_area())
        return layout

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

    def answer_area(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel('回答代码'))
        self.answer_editor = QTextEdit(self)
        layout.addWidget(self.answer_editor)
        return layout

    def operator_area_widget(self):
        search_box = TemplateFileComboBox()
        search_box.template_selected.connect(self.template_switch)
        search_box.setCurrentIndex(0)

        submit_button = QPushButton('生成代码')
        submit_button.clicked.connect(self.submit_question)
        copy_button = QPushButton('复制回答')
        copy_button.clicked.connect(self.copy_answer)
        layout = QVBoxLayout()
        layout.addWidget(search_box)
        layout.addWidget(submit_button)
        layout.addWidget(copy_button)
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
            self.curr_prompt = parse_template(template)
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
        answer = gen_code_question(self.chromium_page, self.curr_prompt, **param_map)
        self.answer_editor.setText(answer)