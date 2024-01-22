import asyncio
import datetime
import json
import subprocess
import sys
import tempfile
import time
from asyncio import Task
from json import JSONDecodeError
from typing import Optional, Any, Callable, Coroutine, Sequence

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Slot, Signal, Qt, QPoint
from PySide6.QtGui import QColor, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QBoxLayout,
    QFrame,
    QTreeView,
    QWidget,
    QApplication,
    QMessageBox,
    QMenu,
    QPushButton,
)

from ..widgets import dialog as my_dialog

JSON_ROOT_PATH = "$"


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

        from ..ui.json_tool_frame_uic import Ui_JsonToolFrame

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

        my_dialog.show_input_dialog(
            "更改标签名",
            "新名称",
            self,
            text_value=self.ui.tabWidget.tabText(index),
            text_value_select_callback=_rename,
        )

    def init_task_cancel_shortcut(self):
        def _cancel_task():
            while self.task_info_list:
                self.task_info_list.pop().cancel()

        QShortcut(QKeySequence.StandardKey.Cancel, self, _cancel_task)

    @Slot()
    def import_from_paste(self):
        self.add_json_viewer_tab(
            "粘贴内容", lambda: json.loads(QApplication.clipboard().text())
        )

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
            self.add_json_viewer_tab("命令输出", lambda: _get_json_from_shell(command))

        async def _get_json_from_shell(command: str) -> Any:
            with tempfile.TemporaryFile() as out_file:
                popen = subprocess.Popen(
                    f"{command} && echo done >&2 ", shell=True, stdout=out_file
                )
                while popen.poll() is None:
                    await asyncio.sleep(1)
                out_file.seek(0)
                output = str(out_file.read(), "utf-8")
                return json.loads(output)

        my_dialog.show_multi_line_input_dialog(
            "执行shell命令", "command", self, text_value_select_callback=_import_from_shell
        )

    def set_import_enable(self, enable):
        for child in self.children():
            if isinstance(child, QPushButton) and "JSON" in child.text():
                child.setEnabled(enable)


class JsonViewerFrame(QFrame):
    messageChanged = Signal(str)
    jsonChanged = Signal()
    refresh_task: CancelableTask = None

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        data: Any = None,
        data_func: Callable[[], Any] = None,
    ):
        super().__init__(parent)

        from ..ui.json_viewer_frame_uic import Ui_JsonViewerFrame

        self.ui = Ui_JsonViewerFrame()
        self.ui.setupUi(self)

        self.data = data
        self.data_func = data_func
        self.init_refreshing_json()

    def init_refreshing_json(self):
        def _refresh_or_cancel():
            refresh_btn = self.ui.refresh_btn
            if self.refresh_task and self.refresh_task.is_running():
                self.refresh_task.cancel()
                while self.refresh_task.is_running():
                    time.sleep(0.1)
                return
            try:
                data = self.data_func()
            except JSONDecodeError as e:
                detail = (
                    f"Line: {e.lineno}/{len(e.doc.splitlines())}\n"
                    f"{e.doc[max(0, e.pos - 10):min(e.pos + 10, len(e.doc))]}"
                )
                my_dialog.show_message(
                    QMessageBox.Icon.Critical,
                    "Error",
                    e.msg,
                    parent=self,
                    detail=detail,
                )
                return
            if not isinstance(data, Coroutine):
                _set_data_then_fresh(data)
                self.jsonChanged.emit()
                return
            refresh_btn.setText("取消刷新")
            self.refresh_task = CancelableTask.create_task(
                f"refresh-json-{self.data_func.__name__}",
                _wait_data_then_refresh(data),
                lambda: refresh_btn.setText("刷新"),
            )

        async def _wait_data_then_refresh(future: Coroutine):
            _set_data_then_fresh(await future)
            self.jsonChanged.emit()

        def _set_data_then_fresh(data: Any):
            if not data:
                return
            self.update_json_tree(data)
            curr = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.messageChanged.emit(f"于{curr}刷新")

        if self.data_func:
            _refresh_or_cancel()
            self.ui.refresh_btn.clicked.connect(_refresh_or_cancel)
        else:
            self.ui.refresh_btn.setEnabled(False)
            self.update_json_tree(self.data)

    def update_json_tree(self, data: Any):
        json_data_frame = self.ui.json_data_frame
        json_data_frame.update_data(data)
        json_data_frame.search()


class JsonModelItem:
    def __init__(
        self,
        row: int,
        key: str,
        value: Any,
        parent_row: int,
        parent_item: Optional["JsonModelItem"],
    ):
        self.row = row
        self.key = key
        self.value = value
        self.parent_row = parent_row
        self.parent_item = parent_item
        self._children: list[JsonModelItem] = (
            [None] * len(value) if isinstance(value, (list, dict)) else []
        )

    def child_count(self) -> int:
        return len(self._children)

    def data(self, index: QModelIndex, role=-1) -> Any:
        item_data = dict[int, Any]()
        if index.column() == 0:
            item_data.update(
                {
                    Qt.ItemDataRole.DisplayRole: self.key,
                    Qt.ItemDataRole.EditRole: self.key,
                }
            )
        elif index.column() == 1:
            if isinstance(self.value, (list, dict)):
                item_data.update(
                    {
                        Qt.ItemDataRole.DisplayRole: f"<{type(self.value).__name__}({len(self.value)})>",
                        Qt.ItemDataRole.ForegroundRole: QColor(
                            Qt.GlobalColor.lightGray
                        ),
                    }
                )
            elif self.value is not None:
                item_data.update(
                    {
                        Qt.ItemDataRole.DisplayRole: str(self.value),
                        Qt.ItemDataRole.EditRole: self.value,
                        Qt.ItemDataRole.ToolTipRole: str(self.value),
                    }
                )
        return item_data.get(role)

    def parent_index(self, model: QAbstractItemModel) -> QModelIndex:
        return model.createIndex(self.parent_row, 0, self.parent_item)

    def child_item(self, row: int) -> Optional["JsonModelItem"]:
        if len(self._children) <= row:
            return None
        if self._children[row] is not None:
            return self._children[row]
        key, value = self.row_kv(row)
        self._children[row] = JsonModelItem(row, key, value, self.row, self)
        return self._children[row]

    def row_kv(self, row: int) -> Optional[tuple]:
        if isinstance(self.value, dict):
            key_list = sorted(list(self.value.keys()))
            return key_list[row], self.value[key_list[row]]
        elif isinstance(self.value, list):
            return f"[{row}]", self.value[row]
        return None


class JsonItemModel(QAbstractItemModel):
    def __init__(self, parent: QWidget, data: Any):
        super().__init__(parent)
        self.root_item = JsonModelItem(0, "$", data, -1, None)

    def update_data(self, data: Any):
        self.root_item = JsonModelItem(0, "$", data, -1, None)
        self.layoutChanged.emit()

    def columnCount(self, parent: QModelIndex = None) -> int:
        return 2

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if not parent.isValid():
            return 1
        parent_item: JsonModelItem = parent.internalPointer()
        return parent_item.child_count()

    def index(
        self, row: int, column: int, parent: QModelIndex = QModelIndex()
    ) -> QModelIndex:
        if not parent.isValid():
            item = self.root_item
        else:
            parent_item: JsonModelItem = parent.internalPointer()
            item = parent_item.child_item(row)
        return self.createIndex(row, column, item)

    def parent(self, child: QModelIndex = None) -> QModelIndex:
        item: JsonModelItem = child.internalPointer()
        if not item:
            return QModelIndex()
        return item.parent_index(self)

    def data(self, index: QModelIndex, role=-1) -> Any:
        item: JsonModelItem = index.internalPointer()
        return item.data(index, role) if item else None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = -1
    ) -> Any:
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            return ("键", "值")[section]
        return None


class JsonTreeView(QTreeView):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._model = JsonItemModel(self, None)
        self.setModel(self._model)
        self._model.dataChanged.connect(lambda *args: self.resizeColumnToContents(0))
        self.setup_menu()

    def update_data(self, data: Any):
        self._model.update_data(data)

    def recursively_search_columns(
        self, index: QModelIndex, keywords: Sequence[str]
    ) -> bool:
        def _match(_index: QModelIndex):
            _text = self._model.data(_index, Qt.ItemDataRole.DisplayRole)
            return _text and keywords[_index.column()].lower() in _text.lower()

        model = self._model
        if all(
            map(
                lambda column: _match(model.index(index.row(), column, index.parent())),
                range(model.columnCount(index)),
            )
        ):
            self.set_all_show_able(index)
            self.expand_self_and_collapse_children(index)
            return True

        if model.rowCount(index):
            any_child_match = any(
                list(
                    map(
                        lambda child: self.recursively_search_columns(child, keywords),
                        map(
                            lambda row: model.index(row, index.column(), index),
                            range(model.rowCount(index)),
                        ),
                    )
                )
            )
        else:
            any_child_match = False
        self.setExpanded(index, any_child_match)
        self.setRowHidden(index.row(), index.parent(), not any_child_match)
        return any_child_match

    def expand_self_and_collapse_children(self, index: QModelIndex):
        self.expand(index)
        model = self._model
        children = [
            model.createIndex(i, index.column(), index)
            for i in range(model.rowCount(index))
        ]
        for child in children:
            self.collapse(child)

    def set_all_show_able(self, index: QModelIndex):
        model = self._model
        self.setRowHidden(index.row(), index.parent(), False)
        children = [
            model.index(row, index.column(), index)
            for row in range(model.rowCount(index))
        ]
        for child in children:
            self.set_all_show_able(child)

    def show_children(self, index: QModelIndex):
        model = self._model
        children = [
            model.index(row, index.column(), index)
            for row in range(model.rowCount(index))
        ]
        self.expand(index)
        for child in children:
            self.setRowHidden(child.row(), child.parent(), False)
            self.collapse(child)

    def setup_menu(self):
        def _popup_item_menu(pos: QPoint):
            index = self.indexAt(pos)
            if not (index and index.isValid()):
                return
            menu = QMenu(self)
            menu.addAction("Copy").triggered.connect(
                lambda: _copy_to_clipboard(
                    self.model().data(index, Qt.ItemDataRole.EditRole)
                )
            )
            menu.addAction("Show Children").triggered.connect(
                lambda: self.show_children(index)
            )
            item = index.internalPointer()
            if isinstance(item, JsonModelItem):
                menu.addAction("Copy JSON Value").triggered.connect(
                    lambda: _copy_to_clipboard(item.value)
                )
                menu.addAction("Show Value As New Frame").triggered.connect(
                    lambda: _show_value_as_new_frame(item.key, item.value)
                )
                if isinstance(item.value, str):
                    menu.addAction("Parse Value As Json And Show").triggered.connect(
                        lambda: _show_value_as_new_frame(item.key, json.loads(item.value))
                    )
            menu.exec(self.mapToGlobal(pos))
            menu.deleteLater()

        def _copy_to_clipboard(content):
            if isinstance(content, list) or isinstance(content, dict):
                content = json.dumps(content, indent=2, ensure_ascii=False)
            else:
                content = str(content)
            QApplication.clipboard().setText(content)

        def _show_value_as_new_frame(json_key, json_value: Any):
            frame = JsonDataFrame(json_value, self)
            frame.setWindowFlag(Qt.WindowType.Window)
            frame.setWindowTitle(f"响应体: key={json_key}")
            frame.setFixedSize(800, 600)
            frame.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            frame.show()

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(_popup_item_menu)

    def search(self, key_search_word: str, value_search_word: str):
        model: JsonItemModel = self.model()
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            self.recursively_search_columns(
                index,
                [key_search_word, value_search_word],
            )


class JsonDataFrame(QFrame):
    def __init__(self, data: Any = dict(), parent: Optional[QWidget] = None):
        super().__init__(parent)

        from .simple_json_frame_uic import Ui_Frame

        self.ui = Ui_Frame()
        self.ui.setupUi(self)
        tree_view = self.ui.json_tree_view
        tree_view.header().sectionResized.connect(self.resize_search_widgets)
        tree_view.header().geometriesChanged.connect(self.resize_search_widgets)

        self.update_data(data)

    def update_data(self, data):
        tree_view = self.ui.json_tree_view
        tree_view.update_data(data)

        tree_view.expand_self_and_collapse_children(tree_view.model().index(0, 0))
        tree_view.resizeColumnToContents(0)

    def resize_search_widgets(self, *_):
        tree_view = self.ui.json_tree_view
        layout: QBoxLayout = self.ui.search_edits_area_widget.layout()
        for column in range(tree_view.model().columnCount()):
            layout.setStretch(column, tree_view.columnWidth(column))

    @Slot(str)
    def search(self, *_):
        key_search_word = self.ui.key_search_edit.text()
        value_search_word = self.ui.value_search_edit.text()
        tree_view = self.ui.json_tree_view
        tree_view.search(key_search_word, value_search_word)


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
