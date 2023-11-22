import asyncio
import datetime
import json
import subprocess
import sys
import tempfile
import time
from asyncio import Task
from json import JSONDecodeError
from typing import Optional, Any, Callable, Coroutine

import jsonpath
from PySide6.QtCore import Slot, Signal, Qt, QPoint
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import QFrame, QWidget, QTreeWidgetItem, QApplication, QMessageBox, QMenu, \
    QInputDialog, QLineEdit, QPushButton

import mywidgets.dialog as my_dialog

JSON_ROOT_PATH = '$'


class CancelableTask:
    def __init__(self, task: Task, cancel_callback: Callable[[], None]):
        self.task = task
        self.cancel_callback = cancel_callback

    @staticmethod
    def create_task(name: str, future: Coroutine, final_func: Callable):
        async def _run():
            await future
            final_func()

        task = asyncio.create_task(_run(), name=name)
        return CancelableTask(task, final_func)

    def cancel(self):
        self.task.cancel()
        self.cancel_callback()

    def is_running(self) -> bool:
        return not self.task.cancelled() and not self.task.done()


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
        self.add_json_viewer_tab('粘贴内容', lambda: json.loads(QApplication.clipboard().text()))

    def add_json_viewer_tab(self, name: str, data_func: Any):
        tab_widget = self.ui.tabWidget
        frame = JsonViewerFrame(tab_widget, data_func=data_func)
        tab_widget.addTab(frame, name)
        tab_widget.setCurrentIndex(tab_widget.count() - 1)

    @Slot()
    def import_from_shell(self):
        def _import_from_shell(command: str):
            if not command:
                return
            self.add_json_viewer_tab('命令输出', lambda: _get_json_from_shell(command))

        async def _get_json_from_shell(command: str) -> Any:
            with tempfile.TemporaryFile() as out_file:
                popen = subprocess.Popen(f'{command} && echo done >&2 ', shell=True, stdout=out_file)
                while popen.poll() is None:
                    await asyncio.sleep(1)
                out_file.seek(0)
                output = str(out_file.read(), 'utf-8')
                return json.loads(output)

        my_dialog.show_multi_line_input_dialog('执行shell命令', 'command', self,
                                               text_value_select_callback=_import_from_shell)

    def set_import_enable(self, enable):
        for child in self.children():
            if isinstance(child, QPushButton) and 'JSON' in child.text():
                child.setEnabled(enable)


class JsonViewerFrame(QFrame):
    USER_DATA_ITEM_COL = 0
    JSON_VALUE_COLUMN = 1
    JSON_PATH_ROLE = Qt.ItemDataRole.UserRole + 1
    jsonPathChanged = Signal(str)
    messageChanged = Signal(str)
    refresh_task: CancelableTask = None

    def __init__(self, parent: Optional[QWidget] = None, *,
                 data: Any = None,
                 data_func: Callable[[], Any] = None):
        super().__init__(parent)

        from ui.json_viewer_frame_uic import Ui_JsonViewerFrame
        self.ui = Ui_JsonViewerFrame()
        self.ui.setupUi(self)

        self.data = data
        self.data_func = data_func
        self.init_menu()
        self.init_refreshing_json()

    def init_refreshing_json(self):
        def _refresh_or_cancel():
            refresh_btn = self.ui.refresh_btn
            if self.refresh_task and self.refresh_task.is_running():
                self.refresh_task.cancel()
                while self.refresh_task.is_running():
                    time.sleep(.1)
                return
            try:
                data = self.data_func()
            except JSONDecodeError as e:
                detail = (f'Line: {e.lineno}/{len(e.doc.splitlines())}\n'
                          f'{e.doc[max(0, e.pos - 10):min(e.pos + 10, len(e.doc))]}')
                my_dialog.show_message(QMessageBox.Icon.Critical, 'Error', e.msg,
                                       parent=self,
                                       detail=detail)
                return
            if not isinstance(data, Coroutine):
                _set_data_then_fresh(data)
                return
            refresh_btn.setText('取消刷新')
            self.refresh_task = CancelableTask.create_task(f'refresh-json-{self.data_func.__name__}',
                                                           _wait_data_then_refresh(data),
                                                           lambda: refresh_btn.setText('刷新'))

        async def _wait_data_then_refresh(future: Coroutine):
            _set_data_then_fresh(await future)

        def _set_data_then_fresh(data: Any):
            if not data:
                return
            self.data = data
            self.refresh_json_tree(self.ui.json_path_edit_widget.text())
            curr = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.messageChanged.emit(f'于{curr}刷新')

        if self.data_func:
            _refresh_or_cancel()
            self.ui.refresh_btn.clicked.connect(_refresh_or_cancel)
        else:
            self.ui.refresh_btn.setEnabled(False)
            self.refresh_json_tree()

    def refresh_json_tree(self, json_path=JSON_ROOT_PATH):
        self.update_json_tree(self.data)
        if json_path:
            self.jsonPathChanged.emit(json_path)

    def update_json_tree(self, data: Any, json_path=JSON_ROOT_PATH):
        tree_widget = self.ui.json_tree_widget
        tree_widget.clear()

        item = QTreeWidgetItem(tree_widget, [json_path])
        item.setData(self.USER_DATA_ITEM_COL, self.JSON_PATH_ROLE, json_path)
        tree_widget.addTopLevelItem(item)
        self.create_sub_items(item, data, json_path)
        if item.childCount() > 0:
            item.setExpanded(True)
        else:
            item.setText(self.JSON_VALUE_COLUMN, str(data))
        self.search_json(self.ui.search_text_edit_widget.text())
        tree_widget.resizeColumnToContents(0)

    def create_sub_items(self, parent: QTreeWidgetItem, data, json_path: str):
        if isinstance(data, dict):
            for key, value in data.items():
                item = QTreeWidgetItem(parent, [key])
                parent.addChild(item)
                item_path = f'{json_path}.{key}'
                item.setData(self.USER_DATA_ITEM_COL, self.JSON_PATH_ROLE, item_path)
                self.create_sub_items(item, value, item_path)
                if not item.childCount():
                    item.setText(self.JSON_VALUE_COLUMN, str(value))
                else:
                    item.setExpanded(True)
        elif isinstance(data, list):
            for index, value in enumerate(data):
                item = QTreeWidgetItem(parent, [f'[{index}]'])
                parent.addChild(item)
                item_path = f'{json_path}[{index}]'
                item.setData(self.USER_DATA_ITEM_COL, self.JSON_PATH_ROLE, item_path)
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
            menu.addAction('Copy Key').triggered.connect(lambda: _copy_to_clipboard(item.text(0)))
            menu.addAction("Copy Value").triggered.connect(lambda: _copy_to_clipboard(item.text(1)))
            menu.addAction("Copy JSON Value").triggered.connect(lambda: _copy_to_clipboard(
                self._item_json_value(item)))
            menu.exec(widget.mapToGlobal(pos))
            menu.deleteLater()

        def _copy_to_clipboard(content):
            if isinstance(content, list) or isinstance(content, dict):
                content = json.dumps(content, indent=2, ensure_ascii=False)
            else:
                content = str(content)
            QApplication.clipboard().setText(content)

        widget = self.ui.json_tree_widget
        widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        widget.customContextMenuRequested.connect(_popup_item_menu)

    def _item_json_value(self, item: QTreeWidgetItem):
        json_path = item.data(0, self.JSON_PATH_ROLE)
        if JSON_ROOT_PATH == json_path:
            return self.data
        return jsonpath.jsonpath(self.data, json_path)[0]

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
        tree_widget.resizeColumnToContents(0)

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
        self.go_json_path(json_path)

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
        view_root_path = self.ui.json_tree_widget.topLevelItem(0).data(self.USER_DATA_ITEM_COL, self.JSON_PATH_ROLE)
        if not json_path or view_root_path == json_path:
            edit_widget.setStyleSheet('')
            return
        data = self.data if json_path == JSON_ROOT_PATH else jsonpath.jsonpath(self.data, json_path)
        data = data[0] if isinstance(data, list) and len(data) == 1 else data
        if data:
            self.update_json_tree(data, json_path)
            edit_widget.setStyleSheet('')
            if json_path != edit_widget.text():
                edit_widget.setText(json_path)
            return
        if json_path == edit_widget.text():
            edit_widget.setStyleSheet('background-color:pink;')
            return
        my_dialog.show_message(QMessageBox.Icon.Critical, 'Error', 'JSON Path无有效数据',
                               parent=self.ui.json_tree_widget)


def main():
    from PySide6.QtAsyncio import QAsyncioEventLoopPolicy
    app = QApplication()
    frame = JsonToolFrame()
    frame.show()

    asyncio.set_event_loop_policy(QAsyncioEventLoopPolicy())
    future = asyncio.get_event_loop().create_future()
    app.lastWindowClosed.connect(lambda: future.set_result(True))
    asyncio.get_event_loop().run_until_complete(future)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
