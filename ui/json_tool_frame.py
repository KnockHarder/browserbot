import asyncio
import datetime
import json
import subprocess
import sys
import tempfile
from asyncio import Task
from json import JSONDecodeError
from typing import Optional, Union, Any, Callable, IO

import jsonpath
from PySide6.QtCore import Slot, Signal, Qt, QPoint
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import QFrame, QWidget, QTreeWidgetItem, QApplication, QMessageBox, QTreeWidget, QMenu, \
    QInputDialog, QLineEdit, QPushButton

import mywidgets.dialog as my_dialog


class CancelableTask:
    def __init__(self, task: Task, cancel_callback: Callable[[], None]):
        self.task = task
        self.cancel_callback = cancel_callback

    def cancel(self):
        self.task.cancel()
        self.cancel_callback()


class JsonToolFrame(QFrame):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        from ui.json_tool_frame_uic import Ui_JsonToolFrame
        self.ui = Ui_JsonToolFrame()
        self.ui.setupUi(self)

        tab_widget = self.ui.tabWidget
        tab_widget.tabBarDoubleClicked.connect(self.rename_tab)
        tab_widget.tabCloseRequested.connect(lambda idx: tab_widget.removeTab(idx))
        self.task_info_list = list[CancelableTask]()
        self.init_task_cancel_shortcut()

    def rename_tab(self, index: int):
        def _rename(name: str):
            if not name:
                return
            self.ui.tabWidget.setTabText(index, name)

        my_dialog.show_input_dialog('更改标签名', '新名称', self,
                                    text_value=self.ui.tabWidget.tabText(index),
                                    text_value_select_callback=_rename)

    def init_task_cancel_shortcut(self):
        def _cancel_task():
            while self.task_info_list:
                self.task_info_list.pop().cancel()

        QShortcut(QKeySequence.StandardKey.Cancel, self, _cancel_task)

    @Slot()
    def import_from_paste(self):
        text = QApplication.clipboard().text()
        try:
            data = json.loads(text)
            self.import_json(data)
        except JSONDecodeError as e:
            box = QMessageBox(QMessageBox.Icon.Critical, 'Error', e.msg,
                              QMessageBox.StandardButton.Close, self)
            box.setDetailedText(f'Line: {e.lineno}/{len(text.splitlines())}\n'
                                f'{text[max(0, e.pos - 10):min(e.pos + 10, len(text))]}')
            box.setWindowModality(Qt.WindowModality.WindowModal)
            box.show()

    def import_json(self, data: Union[dict, list, Any], tab_name: str = None):
        tab_widget = self.ui.tabWidget
        if not tab_name:
            now = datetime.datetime.now()
            tab_name = f'{now.hour}:{now.minute}'
        tab_widget.addTab(JsonViewerFrame(data, tab_widget), tab_name)

    @Slot()
    def import_from_shell(self):
        def _exec_shell(command: str):
            if not command:
                return
            out_file = tempfile.TemporaryFile()
            popen = subprocess.Popen(f'{command} && echo done >&2 ', shell=True, stdout=out_file)
            self.set_import_enable(False)
            task = asyncio.create_task(_async_import_from_output(popen, out_file), name='import_from_shell')
            self.task_info_list.append(CancelableTask(task, lambda: self.set_import_enable(True)))

        async def _async_import_from_output(popen: subprocess.Popen[bytes], out_file: IO[bytes]):
            while popen.poll() is None:
                await asyncio.sleep(1)
            out_file.seek(0)
            _update_json_by_output(str(out_file.read(), 'utf-8'), popen.poll())
            self.set_import_enable(True)

        def _update_json_by_output(output: str, code: int):
            if not output:
                box = QMessageBox(QMessageBox.Icon.Warning, 'Error', '无输出内容',
                                  QMessageBox.StandardButton.Close, self)
                box.setDetailedText(f'Code: {code}')
                box.setWindowModality(Qt.WindowModality.WindowModal)
                box.show()
                return
            try:
                self.import_json(json.loads(output))
            except JSONDecodeError:
                box = QMessageBox(QMessageBox.Icon.Critical, 'Error', '非JSON格式输出',
                                  QMessageBox.StandardButton.Close, self)
                box.setDetailedText(output[0: min(20, len(output))])
                box.setWindowModality(Qt.WindowModality.WindowModal)
                box.show()

        my_dialog.show_multi_line_input_dialog('执行shell命令', 'command', self,
                                               text_value_select_callback=_exec_shell)

    def set_import_enable(self, enable):
        for child in self.children():
            if isinstance(child, QPushButton) and 'JSON' in child.text():
                child.setEnabled(enable)


class JsonViewerFrame(QFrame):
    JSON_VALUE_COLUMN = 1
    JSON_PATH_ROLE = Qt.ItemDataRole.UserRole + 1
    jsonPathChanged = Signal(str)

    def __init__(self, data: Union[dict, list, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.data = data
        from ui.json_viewer_frame_uic import Ui_JsonViewerFrame
        self.ui = Ui_JsonViewerFrame()
        self.ui.setupUi(self)
        self.refresh_json_tree()
        self.init_menu()

    def refresh_json_tree(self, json_path='$'):
        self.update_json_tree(self.data)
        if json_path:
            self.jsonPathChanged.emit(json_path)

    def update_json_tree(self, data: Union[dict, list, Any], json_path='$'):
        tree_widget = self.ui.json_tree_widget
        tree_widget.clear()
        self.create_sub_items(tree_widget, data, json_path)
        if not tree_widget.topLevelItemCount():
            tree_widget.addTopLevelItem(QTreeWidgetItem(tree_widget, [str(data)]))
        self.jsonPathChanged.emit(json_path)
        self.search_json(self.ui.search_text_edit_widget.text())
        tree_widget.resizeColumnToContents(0)

    def create_sub_items(self, parent: Union[QTreeWidget, QTreeWidgetItem], data, json_path: str):
        def _add_child(_item: QTreeWidgetItem):
            if isinstance(parent, QTreeWidget):
                parent.addTopLevelItem(_item)
            else:
                parent.addChild(_item)

        if isinstance(data, dict):
            for key, value in data.items():
                item = QTreeWidgetItem(parent, [key])
                _add_child(item)
                item_path = f'{json_path}.{key}'
                item.setData(0, self.JSON_PATH_ROLE, item_path)
                self.create_sub_items(item, value, item_path)
                if not item.childCount():
                    item.setText(self.JSON_VALUE_COLUMN, str(value))
                else:
                    item.setExpanded(True)
        elif isinstance(data, list):
            for index, value in enumerate(data):
                item = QTreeWidgetItem(parent, [f'[{index}]'])
                _add_child(item)
                item_path = f'{json_path}[{index}]'
                item.setData(0, self.JSON_PATH_ROLE, item_path)
                self.create_sub_items(item, value, item_path)
                if not item.childCount():
                    item.setText(self.JSON_VALUE_COLUMN, str(value))
                else:
                    item.setExpanded(True)

    def init_menu(self):
        def _copy_to_clipboard(content):
            if isinstance(content, list) or isinstance(content, dict):
                content = json.dumps(content, indent=2, ensure_ascii=False)
            else:
                content = str(content)
            QApplication.clipboard().setText(content)

        def _popup_item_menu(pos: QPoint):
            item = widget.itemAt(pos)
            if not item:
                return
            menu = QMenu()
            menu.addAction('Focus').triggered.connect(lambda: self.focus_item(item))
            menu.addAction('Show Descendants').triggered.connect(lambda: self.show_and_expand_recursively(item))
            menu.addAction('Go path').triggered.connect(lambda: self.input_and_go_json_path(item))
            menu.addAction('Copy Key').triggered.connect(lambda: _copy_to_clipboard(item.text(0)))
            menu.addAction("Copy Value").triggered.connect(lambda: _copy_to_clipboard(item.text(1)))
            menu.addAction("Copy JSON Value").triggered.connect(lambda: _copy_to_clipboard(
                self._item_json_value(item)))
            menu.exec(widget.mapToGlobal(pos))
            menu.deleteLater()

        widget = self.ui.json_tree_widget
        widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        widget.customContextMenuRequested.connect(_popup_item_menu)

    def _item_json_value(self, item: QTreeWidgetItem):
        return jsonpath.jsonpath(self.data, item.data(0, self.JSON_PATH_ROLE))[0]

    def show_and_expand_recursively(self, item: QTreeWidgetItem):
        item.setExpanded(True)
        item.setHidden(False)
        for i in range(item.childCount()):
            self.show_and_expand_recursively(item.child(i))

    @Slot(str)
    def search_json(self, key: str):
        tree_widget = self.ui.json_tree_widget
        for index in range(tree_widget.topLevelItemCount()):
            item = tree_widget.topLevelItem(index)
            item.setHidden(self.non_child_match(key, item))

    def non_child_match(self, key: str, parent: QTreeWidgetItem):
        non_child_match = True
        if parent.childCount():
            for i in range(parent.childCount()):
                child = parent.child(i)
                child.setHidden(self.non_child_match(key, child))
                non_child_match &= child.isHidden()
        if non_child_match:
            any_match = any(map(lambda x: x and key.lower() in x.lower(),
                                [parent.text(i) for i in range(parent.columnCount())]))
            return not any_match
        else:
            return False

    def focus_item(self, item: QTreeWidgetItem):
        json_path = item.data(0, self.JSON_PATH_ROLE)
        if not json_path:
            return
        data = jsonpath.jsonpath(self.data, json_path)
        if not data:
            box = QMessageBox(QMessageBox.Icon.Warning, 'Error', '节点无数据',
                              QMessageBox.StandardButton.Close, self.ui.json_tree_widget)
            box.setWindowModality(Qt.WindowModality.WindowModal)
            box.show()
            return
        self.update_json_tree(data[0], json_path)

    def input_and_go_json_path(self, item: QTreeWidgetItem):
        json_path = item.data(0, self.JSON_PATH_ROLE)
        json_path = json_path if json_path else ''
        json_path, confirmed = QInputDialog.getText(
            self.ui.json_tree_widget, '输入JSON Path', 'Path', QLineEdit.EchoMode.Normal,
            json_path, Qt.WindowType.Window)
        if confirmed:
            self.go_json_path(json_path)

    @Slot(str)
    def go_json_path(self, json_path: str):
        edit_widget = self.ui.json_path_edit_widget
        data = jsonpath.jsonpath(self.data, json_path)
        data = data[0] if len(data) == 1 else data
        if data:
            self.update_json_tree(data, json_path)
            edit_widget.setStyleSheet('')
            return
        if json_path == edit_widget.text():
            edit_widget.setStyleSheet('background-color:pink;')
            return
        box = QMessageBox(QMessageBox.Icon.Critical, 'Error', 'JSON Path无有效数据',
                          QMessageBox.StandardButton.Close, self.ui.json_tree_widget)
        box.setWindowModality(Qt.WindowModality.WindowModal)
        box.show()


def main():
    app = QApplication()
    frame = JsonToolFrame()
    frame.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
