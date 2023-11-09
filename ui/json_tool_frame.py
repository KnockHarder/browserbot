import asyncio
import json
import subprocess
import sys
from asyncio import Task
from json import JSONDecodeError
from typing import Optional, Union, Any, Callable

import jsonpath
from PySide6.QtCore import Slot, Signal, Qt, QPoint
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import QFrame, QWidget, QTreeWidgetItem, QApplication, QMessageBox, QTreeWidget, QMenu, \
    QInputDialog, QLineEdit, QPushButton


class CancelableTask:
    def __init__(self, task: Task, cancel_callback: Callable[[], None]):
        self.task = task
        self.cancel_callback = cancel_callback

    def cancel(self):
        self.task.cancel()
        self.cancel_callback()


class JsonViewerFrame(QFrame):
    JSON_VALUE_COLUMN = 1
    JSON_PATH_ROLE = Qt.ItemDataRole.UserRole + 1
    jsonPathChanged = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        from ui.json_tool_frame_uic import Ui_json_viewer_frame
        self.ui = Ui_json_viewer_frame()
        self.ui.setupUi(self)

        self.data = {}
        self.refresh_json_tree()
        self.init_menu()

        self.task_info_list = list[CancelableTask]()
        self.init_task_cancel_shortcut()

    def refresh_json_tree(self):
        self.update_json_tree(self.data)

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
        def _popup_item_menu(pos: QPoint):
            item = widget.itemAt(pos)
            if not item:
                return
            menu = QMenu()
            menu.addAction('Focus').triggered.connect(lambda: self.focus_item(item))
            menu.addAction('Show Descendants').triggered.connect(lambda: self.show_and_expand_recursively(item))
            menu.addAction('Go path').triggered.connect(lambda: self.input_and_go_json_path(item))
            menu.addAction('Copy Key').triggered.connect(lambda: QApplication.clipboard().setText(item.text(0)))
            menu.addAction("Copy Value").triggered.connect(lambda: QApplication.clipboard().setText(item.setText(1)))
            menu.exec(widget.mapToGlobal(pos))
            menu.deleteLater()

        widget = self.ui.json_tree_widget
        widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        widget.customContextMenuRequested.connect(_popup_item_menu)

    def init_task_cancel_shortcut(self):
        def _cancel_task():
            while self.task_info_list:
                self.task_info_list.pop().cancel()

        QShortcut(QKeySequence.StandardKey.Cancel, self, _cancel_task)

    def show_and_expand_recursively(self, item: QTreeWidgetItem):
        item.setExpanded(True)
        item.setHidden(False)
        for i in range(item.childCount()):
            self.show_and_expand_recursively(item.child(i))

    @Slot()
    def import_from_paste(self):
        text = QApplication.clipboard().text()
        try:
            self.data = json.loads(text)
            self.refresh_json_tree()
        except JSONDecodeError as e:
            box = QMessageBox(QMessageBox.Icon.Critical, 'Error', e.msg,
                              QMessageBox.StandardButton.Close, self)
            box.setDetailedText(f'Line: {e.lineno}/{len(text.splitlines())}\n'
                                f'{text[max(0, e.pos - 10):min(e.pos + 10, len(text))]}')
            box.setWindowModality(Qt.WindowModality.WindowModal)
            box.show()

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

    def go_json_path(self, json_path: str):
        data = jsonpath.jsonpath(self.data, json_path)
        if not data:
            box = QMessageBox(QMessageBox.Icon.Critical, 'Error', 'JSON Path无有效数据',
                              QMessageBox.StandardButton.Close, self.ui.json_tree_widget)
            box.setWindowModality(Qt.WindowModality.WindowModal)
            box.show()
            return
        self.update_json_tree(data[0], json_path)

    @Slot()
    def import_from_shell(self):
        dialog = QInputDialog(self)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        command, confirmed = dialog.getMultiLineText(dialog.parent(), '执行shell命令', 'command')
        if not confirmed:
            return
        popen = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        self.set_import_enable(False)

        async def _async_import_from_shell():
            while popen.poll() is None:
                await asyncio.sleep(1)
            out, err = popen.communicate()
            output = str(out, encoding='utf-8')
            if err or not output:
                box = QMessageBox(QMessageBox.Icon.Warning, 'Error', '无输出内容',
                                  QMessageBox.StandardButton.Close, self)
                box.setDetailedText(f'Code: {err}')
                box.setWindowModality(Qt.WindowModality.WindowModal)
                box.show()
                return
            try:
                self.data = json.loads(output)
                self.refresh_json_tree()
            except JSONDecodeError:
                box = QMessageBox(QMessageBox.Icon.Critical, 'Error', '非JSON格式输出',
                                  QMessageBox.StandardButton.Close, self)
                box.setDetailedText(output[0: min(20, len(output))])
                box.setWindowModality(Qt.WindowModality.WindowModal)
                box.show()
            self.set_import_enable(True)

        task = asyncio.create_task(_async_import_from_shell(), name='import_from_shell')
        self.task_info_list.append(CancelableTask(task, lambda: self.set_import_enable(True)))

    def set_import_enable(self, enable):
        for child in self.children():
            if isinstance(child, QPushButton) and 'JSON' in child.text():
                child.setEnabled(enable)


def main():
    app = QApplication()
    frame = JsonViewerFrame()
    frame.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
