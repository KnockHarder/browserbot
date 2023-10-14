import os.path
import sys
from typing import Optional

from PySide6.QtCore import Slot, Signal
from PySide6.QtWidgets import QFrame, QWidget, QFileDialog, QPlainTextEdit, QLineEdit, QLabel, QFormLayout, \
    QApplication, QMessageBox, QInputDialog
from jinja2 import TemplateError
from langchain.prompts import load_prompt, PromptTemplate

from config import get_browser, gpt_prompt_file_dir
from gpt import gpt_util
from gpt.prompt import parse_template


class GptTabFrame(QFrame):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        from ui.gpt_tab_frame_uic import Ui_GptPageFrame
        self.ui = Ui_GptPageFrame()
        self.ui.setupUi(self)

        self.browser = get_browser()

    @Slot()
    def new_chat(self):
        gpt_util.start_new_chat(self.browser)

    @Slot()
    def clear_chat_history(self):
        gpt_util.clear_chat_history(self.browser)


def safe_parse_template(parent: QWidget, template: str) -> Optional[PromptTemplate]:
    try:
        return parse_template(template)
    except (ValueError, TemplateError) as e:
        message_box = QMessageBox(QMessageBox.Icon.Critical, '解析模板失败',
                                  '内容不合法', QMessageBox.StandardButton.Ok, parent)
        message_box.setDetailedText(str(e))
        message_box.open()
        return None


class GptTabCodeGenFrame(QFrame):
    templateTextReset = Signal(str)
    statusLabelTextReset = Signal(str)
    answerTextReset = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        from ui.gpt_tab_code_gen_frame_uic import Ui_CodeGenFrame
        self.ui = Ui_CodeGenFrame()
        self.ui.setupUi(self)

        self.browser = get_browser()
        self.template_file = None

    @Slot()
    def load_template_for_chat(self):
        dialog = QFileDialog(self, '打开模板文件', gpt_prompt_file_dir(), 'JSON Files(*.json)')
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)

        def load_selected_file(path):
            prompt = load_prompt(path)
            self.template_file = path
            self.templateTextReset.emit(prompt.template)
            self.update_variable_form(prompt.template)
            self.statusLabelTextReset.emit(f'加载文件: {path}')

        dialog.fileSelected.connect(load_selected_file)
        dialog.open()

    @Slot()
    def update_for_template_change(self):
        template = self.ui.template_edit.toPlainText()
        self.statusLabelTextReset.emit('模板被修改')
        self.update_variable_form(template)

    def update_variable_form(self, template):
        try:
            prompt = parse_template(template)
        except Exception:
            self.statusLabelTextReset.emit('模板不合法')
            return
        variables = prompt.input_variables
        value_dict = dict()
        variable_form = self.ui.variableForm
        for label, input_widget in [self.get_variable_from_ui(i) for i in range(variable_form.rowCount())]:
            if label.text() in variables:
                value_dict[label.text()] = self.get_input_widget_content(input_widget)
            label.deleteLater()
            input_widget.deleteLater()
        while variable_form.rowCount() > 0:
            variable_form.removeRow(0)
        variable_from_box = self.ui.groupBox

        def create_value_input(l_var: str, value: str, is_last: bool):
            if 'code' in l_var or is_last:
                edit = QPlainTextEdit(variable_from_box)
                set_text_func = edit.setPlainText
            else:
                edit = QLineEdit(variable_from_box)
                set_text_func = edit.setText
            if value:
                set_text_func(value)
            return edit

        for idx, vrb in enumerate(variables):
            label = QLabel(vrb, variable_from_box)
            widget = create_value_input(vrb, value_dict.get(vrb),
                                        idx == len(variables) - 1)
            variable_form.addRow(label, widget)

    @Slot()
    def generate_code(self):
        param_map = dict()
        for i in range(self.ui.variableForm.rowCount()):
            label, input_widget = self.get_variable_from_ui(i)
            content = self.get_input_widget_content(input_widget)
            param_map[label.text()] = content
        template = self.ui.template_edit.toPlainText()
        try:
            prompt = parse_template(template)
        except Exception:
            self.statusLabelTextReset.emit(f'模板不合法，请修正后再提交{template}')
            return
        answer = gpt_util.gen_code_question(self.browser, prompt, **param_map)
        self.answerTextReset.emit(answer)

    @staticmethod
    def get_input_widget_content(input_widget):
        return input_widget.text() if isinstance(input_widget, QLineEdit) \
            else input_widget.toPlainText()

    def get_variable_from_ui(self, row) -> (QLabel, QWidget):
        variable_form = self.ui.variableForm
        label = variable_form.itemAt(row, QFormLayout.ItemRole.LabelRole).widget()
        input_widget = variable_form.itemAt(row, QFormLayout.ItemRole.FieldRole).widget()
        return label, input_widget

    @Slot()
    def save_template(self):
        default_path = self.template_file if self.template_file else gpt_prompt_file_dir()
        dialog = QFileDialog(self, '保存至', default_path, 'JSON Files(*.json')
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)

        def save_template_to_file(path: str):
            template = self.ui.template_edit.toPlainText()
            prompt = safe_parse_template(self, template)
            if not prompt:
                return
            prompt.save(path)

        dialog.fileSelected.connect(save_template_to_file)
        dialog.open()


class GptTemplateManagerFrame(QFrame):
    templateTextReset = Signal(str)
    tipUpdate = Signal(str)
    curr_template_file: str

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        from ui.gpt_tab_template_manager_frame_uic import Ui_TemplateMangerFrame
        self.ui = Ui_TemplateMangerFrame()
        self.ui.setupUi(self)

    @Slot()
    def load_template(self):
        dialog = QFileDialog(self, '打开模板文件', gpt_prompt_file_dir(), 'JSON Files(*.json)')
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.fileSelected.connect(self.load_template_file)
        dialog.open()

    def load_template_file(self, path):
        prompt = load_prompt(path)
        self.set_curr_template_file(path)
        self.templateTextReset.emit(prompt.template)
        self.tipUpdate.emit(f'加载文件: {path}')

    def set_curr_template_file(self, path: str):
        self.curr_template_file = path
        self.ui.rename_file_button.setEnabled(True)

    @Slot()
    def save_template(self):
        default_path = self.curr_template_file \
            if self.curr_template_file else gpt_prompt_file_dir()
        dialog = QFileDialog(self, '保存至', default_path, 'JSON Files(*.json')
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)

        def save_template_to_file(path):
            template = self.ui.plainTextEdit.toPlainText()
            prompt = safe_parse_template(self, template)
            if not prompt:
                return
            prompt.save(path)
            self.set_curr_template_file(path)
            self.tipUpdate.emit(f'模板保存至: {path}')

        dialog.fileSelected.connect(save_template_to_file)
        dialog.open()

    @Slot()
    def rename_template_file(self):
        file_path = self.curr_template_file
        if not file_path:
            self.tipUpdate.emit('请先加载模板文件')
            return
        if not os.path.exists(file_path):
            self.tipUpdate.emit(f'文件已被删除: {file_path}')
            return
        self.load_template_file(file_path)
        new_name, confirmed = QInputDialog.getText(self, '文件重命名', '新的文件名')
        while confirmed:
            new_path = os.path.join(os.path.dirname(file_path), new_name)
            if not os.path.exists(new_path):
                if not new_path.endswith('.json'):
                    new_path += '.json'
                os.rename(file_path, new_path)
                self.set_curr_template_file(new_path)
                self.tipUpdate.emit(f'文件更名为: {new_path}')
                break
            else:
                new_name, confirmed = QInputDialog.getText(self, '文件已存在', '新的文件名')


if __name__ == '__main__':
    def main():
        app = QApplication()
        frame = GptTemplateManagerFrame()
        frame.show()
        sys.exit(app.exec())


    main()