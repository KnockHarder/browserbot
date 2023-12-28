import asyncio
import enum
import json
import socket
from asyncio import AbstractEventLoop
from datetime import datetime
from io import BytesIO
from threading import Thread
from typing import Optional, Any, Sequence
from urllib import parse as url_parse
from urllib.parse import urlparse

import aiohttp
from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, Slot, QPoint
from PySide6.QtGui import QColor, QShortcut
from PySide6.QtWidgets import QFrame, QWidget, QTableView, QTreeView, QBoxLayout, QMenu, QApplication
from requests import Response, PreparedRequest

from ..requests.curl import parse_curl
from ..widgets import dialog as my_dialog


def _setup_tab_widget_layout_style(tab_widget):
    tab_widget.setCurrentIndex(0)
    for widget in filter(lambda w: type(w) is QWidget and w.layout(),
                         map(lambda i: tab_widget.widget(i), range(tab_widget.count()))):
        widget.layout().setContentsMargins(0, 0, 0, 0)
        widget.layout().setSpacing(0)


class ImportContentValueError(Exception):
    def __init__(self, content: str):
        super().__init__(content)


class RequestManagerFrame(QFrame):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._http_event_loop: AbstractEventLoop = asyncio.new_event_loop()
        Thread(name="request-manager-http-thread", target=self._http_thread_event_loop, daemon=True).start()

        from .request_manager_frame_uic import Ui_Frame
        self.ui = Ui_Frame()
        self.ui.setupUi(self)
        while self.ui.main_tab_widget.count() > 0:
            self.ui.main_tab_widget.removeTab(0)
        self.init_shortcuts()

    def _http_thread_event_loop(self):
        asyncio.set_event_loop(self._http_event_loop)
        self._http_event_loop.run_forever()

    @Slot()
    def import_request(self):
        def _do(text: str):
            if not text:
                raise ValueError('不可导入空内容')

            text = text.strip()
            tab_widget = self.ui.main_tab_widget
            if text.lower().startswith('curl'):
                req = parse_curl(text)
                frame = ReqRespFrame(self._http_event_loop, tab_widget)
                frame.update_request(req.prepare())
                index = tab_widget.addTab(frame, urlparse(req.url).path)
                tab_widget.setCurrentIndex(index)
                return
            raise ImportContentValueError(text)

        my_dialog.show_multi_line_input_dialog('导入请求', '内容', self,
                                               text_value_select_callback=_do)

    def init_shortcuts(self):
        for i in range(1, 11):
            QShortcut(f'Alt+{i % 10}', self, lambda _i=i: self.ui.main_tab_widget.setCurrentIndex(_i - 1))


class ReqRespFrame(QFrame):
    _req: PreparedRequest

    def __init__(self, _http_event_loop: AbstractEventLoop, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._http_event_loop = _http_event_loop

        from .req_resp_frame_uic import Ui_ReqRespFrame
        self.ui = Ui_ReqRespFrame()
        self.ui.setupUi(self)
        _setup_tab_widget_layout_style(self.ui.main_tab_widget)
        self.ui.resp_body_type_label.setText('空')

    def update_request(self, req: PreparedRequest):
        self._req = req
        self.update_url_area(req)
        self.ui.basic_info_table_view.update_request(req)
        queries = url_parse.parse_qs(url_parse.urlparse(req.url).query, keep_blank_values=True)
        url_params = {k: v[0] if len(v) == 1 else v for k, v in queries.items()}
        self.ui.req_url_params_frame.update_dict(url_params)
        self.ui.req_headers_frame.update_dict(dict(req.headers))
        self.ui.req_body_frame.update_body(req)

    def update_url_area(self, req: PreparedRequest):
        req_method_box = self.ui.req_method_box
        req_method_box.clear()
        req_method_box.addItems(['GET', 'POST'])
        req_method_box.setCurrentText(str(req.method))
        req_schema_box = self.ui.req_schema_box
        req_schema_box.clear()
        req_schema_box.addItems(['http', 'https'])
        parsed_url = urlparse(req.url)
        req_schema_box.setCurrentText(parsed_url.scheme)
        req_address_input = self.ui.req_address_input
        req_address_input.setText(parsed_url.netloc)
        text_width = req_address_input.fontMetrics().boundingRect(req_address_input.text()).width()
        req_address_input.setMaximumWidth(text_width + 8)
        req_path_input = self.ui.req_path_input
        req_path_input.setText(parsed_url.path)

    def update_response(self, resp: Response):
        self.ui.basic_info_table_view.update_response(resp)
        self.ui.resp_headers_frame.update_dict(dict(resp.headers))
        content_type = resp.headers.get('Content-Type')
        if content_type:
            self.ui.resp_body_type_label.setText(content_type)
            if content_type.split(';')[0] == 'application/json':
                data = json.loads(resp.text)
                layout = self.ui.resp_body_area_widget.layout()
                while layout.count() > 0:
                    item = layout.takeAt(0)
                    if item and item.widget():
                        item.widget().deleteLater()
                layout.addWidget(JsonDataFrame(data, self.ui.resp_body_area_widget))

    @Slot()
    def send_request(self):
        async def _request():
            try:
                future = asyncio.run_coroutine_threadsafe(_send(), self._http_event_loop)
                while not future.done():
                    await asyncio.sleep(0.1)
                self.ui.basic_info_table_view.update_req_end_time(datetime.now())
                self.update_response(future.result())
            finally:
                self.ui.send_btn.setEnabled(True)

        async def _send() -> Response:
            req = self._req
            async with aiohttp.request(req.method, req.url, headers=req.headers, data=req.body) as aio_response:
                return await _covert_response(req, aio_response)

        async def _covert_response(req: PreparedRequest, aio_response: aiohttp.ClientResponse) -> Response:
            response = Response()
            response.status_code = aio_response.status
            response.headers = aio_response.headers
            response.raw = BytesIO(await aio_response.content.read())
            response.url = aio_response.url
            response.encoding = aio_response.charset
            response.history = [_covert_response(req, x) for x in aio_response.history]
            response.reason = aio_response.reason
            response.cookies = aio_response.cookies
            response.request = req
            return response

        self.ui.send_btn.setDisabled(True)
        self.ui.basic_info_table_view.update_req_start_time(datetime.now())
        asyncio.create_task(_request(), name='request-manager-send-request-task')


class DictTableFrame(QFrame):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        from .req_resp_dict_frame_uic import Ui_Frame
        self.ui = Ui_Frame()
        self.ui.setupUi(self)
        self.ui.dict_tabl_view.horizontalHeader().geometriesChanged.connect(self.resize_search_widgets)
        self.ui.dict_tabl_view.horizontalHeader().sectionResized.connect(self.resize_search_widgets)

    def resize_search_widgets(self, *_):
        table_view = self.ui.dict_tabl_view
        for column in range(table_view.horizontalHeader().count()):
            self.ui.search_edits_layout.setStretch(column, table_view.columnWidth(column))

    def update_dict(self, data: dict):
        self.ui.dict_tabl_view.update_dict(data)

    def dict_data(self) -> dict:
        return self.ui.dict_tabl_view.dict_data()

    @Slot(str)
    def search(self, *_):
        tabl_view = self.ui.dict_tabl_view
        model = tabl_view.model()
        for row in range(model.rowCount()):
            all_match = (self.ui.key_search_input.text().lower() in self.cell_display_value(row, 0).lower()
                         and self.ui.value_search_input.text().lower() in self.cell_display_value(row, 1).lower())
            tabl_view.setRowHidden(row, not all_match)

    def cell_display_value(self, row: int, column: int) -> str:
        tabl_view = self.ui.dict_tabl_view
        return tabl_view.model().data(tabl_view.model().index(row, column), Qt.ItemDataRole.DisplayRole)


class DictTableView(QTableView):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._model = DictTableItemModel(dict(), self)
        self.setModel(self._model)
        self._model.dataChanged.connect(lambda *args: self.resizeColumnsToContents())
        self._model.layoutChanged.connect(lambda *args: self.resizeColumnsToContents())

    def update_dict(self, data: dict):
        self._model.update_dict(data)

    def dict_data(self) -> dict:
        return self._model.dict_data


class DictTableItemModel(QAbstractItemModel):
    ITEM_VALUE_TYPE_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, data: dict, parent: QWidget):
        super().__init__(parent)
        self.dict_data = data
        self.editable = False

    def update_dict(self, data: dict):
        self.dict_data = dict(data)
        self.layoutChanged.emit()

    def rowCount(self, parent: QModelIndex = None) -> int:
        return len(self.dict_data)

    def columnCount(self, parent: QModelIndex = None) -> int:
        return 2

    def data(self, index: QModelIndex, role: int = -1) -> Any:
        if not index.isValid():
            return None
        key = self._param_key_at(index)
        if index.column() == 0:
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
                return key
            elif role == self.ITEM_VALUE_TYPE_ROLE:
                return str
        elif index.column() == 1:
            value = self.dict_data[key]
            if isinstance(value, list) and len(value) == 1:
                value = value[0]
            if role == Qt.ItemDataRole.DisplayRole:
                return str(value) if value else None
            elif role == Qt.ItemDataRole.EditRole:
                return value
            elif role == self.ITEM_VALUE_TYPE_ROLE:
                return type(value)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = -1) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return ('键', '值')[section]
        return None

    def _param_key_at(self, index):
        key_list = list(self.dict_data.keys())
        key = key_list[index.row()]
        return key

    def setData(self, index: QModelIndex, value: Any, role: int = -1) -> bool:
        if role == Qt.ItemDataRole.EditRole and index.isValid():
            key = self._param_key_at(index)
            if index.column() == 0:
                self.dict_data[value] = self.dict_data.pop(key)
            elif index.column() == 1:
                self.dict_data[key] = value
            else:
                return False
            self.dataChanged.emit(index, index)
            return True
        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        flags = super().flags(index)
        if self.editable:
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def index(self, row: int, column: int, parent: QModelIndex = None) -> QModelIndex:
        return self.createIndex(row, column)

    def parent(self, child: QModelIndex = None) -> QModelIndex:
        return QModelIndex()


class BasicInfoTableView(DictTableView):
    class Label(enum.StrEnum):
        STATUS_CODE = '状态码'
        STATUS_INFO = '状态信息'
        START_TIME = '请求开始时间'
        END_TIME = '请求结束时间'
        RESPONSE_TIME = '响应时间'
        SERVER = '服务器'
        SERVER_IP = '服务器IP'
        SERVER_PORT = '服务器端口'

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        data = dict()
        for label in self.Label:
            data[label] = ''
        super().update_dict(data)

    def update_request(self, req: PreparedRequest):
        parsed_url = urlparse(req.url)
        model = self.model()
        model.setData(self._get_value_index(self.Label.SERVER),
                      parsed_url.hostname, Qt.ItemDataRole.EditRole)
        model.setData(self._get_value_index(self.Label.SERVER_IP), socket.gethostbyname(parsed_url.hostname),
                      Qt.ItemDataRole.EditRole)
        model.setData(self._get_value_index(self.Label.SERVER_PORT), parsed_url.port, Qt.ItemDataRole.EditRole)

    def _get_value_index(self, label: Label):
        model = self.model()
        return model.createIndex(list(self.Label).index(label), 1)

    def update_response(self, resp: Response):
        model = self.model()
        model.setData(self._get_value_index(self.Label.STATUS_CODE), resp.status_code, Qt.ItemDataRole.EditRole)
        model.setData(self._get_value_index(self.Label.STATUS_INFO), resp.reason, Qt.ItemDataRole.EditRole)

    def update_req_start_time(self, req_start_time: datetime):
        model = self.model()
        model.setData(self._get_value_index(self.Label.START_TIME), req_start_time, Qt.ItemDataRole.EditRole)
        model.setData(self._get_value_index(self.Label.END_TIME), None, Qt.ItemDataRole.EditRole)

    def update_req_end_time(self, req_end_time: datetime):
        model = self.model()
        model.setData(self._get_value_index(self.Label.END_TIME), req_end_time, Qt.ItemDataRole.EditRole)
        start_time = self.model().data(self._get_value_index(self.Label.START_TIME), Qt.ItemDataRole.EditRole)
        diff = req_end_time - start_time
        model.setData(self._get_value_index(self.Label.RESPONSE_TIME), diff, Qt.ItemDataRole.EditRole)


class ReqBodyFrame(QFrame):
    class UnsupportedContentTypeError(Exception):
        def __init__(self, content_type: str):
            super().__init__(f'Unsupported content type: {content_type}')

    content_type: str
    data: Any

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        from .req_body_frame_uic import Ui_Frame
        self.ui = Ui_Frame()
        self.ui.setupUi(self)
        _setup_tab_widget_layout_style(self.ui.req_body_tab_widget)

    def update_body(self, req: PreparedRequest):
        content_type = req.headers.get('Content-Type')
        tab_widget = self.ui.req_body_tab_widget
        # find tab by text
        for idx in range(tab_widget.count()):
            widget = tab_widget.widget(idx).layout().itemAt(0).widget()
            if tab_widget.tabText(idx) in content_type.split('/') and hasattr(widget, '__update_body__'):
                widget.__update_body__(req.body)
                tab_widget.setCurrentIndex(idx)
                return
        raise self.UnsupportedContentTypeError(content_type)

    def body_data(self) -> Any:
        tab_widget = self.ui.req_body_tab_widget
        widget = tab_widget.currentWidget()
        return widget.__body_data__()


class DictTableBodyFrame(DictTableFrame):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

    def __update_body__(self, data):
        params_dict = {k: v[0] if len(v) == 0 else v
                       for k, v in url_parse.parse_qs(data, keep_blank_values=True).items()}
        super().update_dict(params_dict)

    def __body_data__(self) -> Any:
        return super().dict_data()


class JsonModelItem:
    def __init__(self, row: int, key: str, value: Any, parent_row: int, parent_item: Optional["JsonModelItem"]):
        self.row = row
        self.key = key
        self.value = value
        self.parent_row = parent_row
        self.parent_item = parent_item
        self._children: list[JsonModelItem] = ([None] * len(value)
                                               if isinstance(value, (list, dict))
                                               else [])

    def child_count(self) -> int:
        return len(self._children)

    def data(self, index: QModelIndex, role=-1) -> Any:
        item_data = dict[int, Any]()
        if index.column() == 0:
            item_data.update({
                Qt.ItemDataRole.DisplayRole: self.key,
                Qt.ItemDataRole.EditRole: self.key
            })
        elif index.column() == 1:
            if isinstance(self.value, (list, dict)):
                item_data.update({
                    Qt.ItemDataRole.DisplayRole: f'<{type(self.value).__name__}({len(self.value)})>',
                    Qt.ItemDataRole.ForegroundRole: QColor(Qt.GlobalColor.lightGray),
                })
            elif self.value is not None:
                item_data.update({
                    Qt.ItemDataRole.DisplayRole: str(self.value),
                    Qt.ItemDataRole.EditRole: self.value,
                    Qt.ItemDataRole.ToolTipRole: str(self.value),
                })
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
            return f'[{row}]', self.value[row]
        return None


class JsonItemModel(QAbstractItemModel):
    def __init__(self, parent: QWidget, data: Any):
        super().__init__(parent)
        self.root_item = JsonModelItem(0, '$', data, -1, None)

    def update_data(self, data: Any):
        self.root_item = JsonModelItem(0, '$', data, -1, None)
        self.layoutChanged.emit()

    def columnCount(self, parent: QModelIndex = None) -> int:
        return 2

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if not parent.isValid():
            return 1
        parent_item: JsonModelItem = parent.internalPointer()
        return parent_item.child_count()

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
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

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = -1) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return ('键', '值')[section]
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

    def recursively_search_columns(self, index: QModelIndex, keywords: Sequence[str]) -> bool:
        def _match(_index: QModelIndex):
            _text = self._model.data(_index, Qt.ItemDataRole.DisplayRole)
            return _text and keywords[_index.column()].lower() in _text.lower()

        model = self._model
        if all(map(lambda column: _match(model.index(index.row(), column, index.parent())),
                   range(model.columnCount(index)))):
            self.set_all_show_able(index)
            self.expand_self_and_collapse_children(index)
            return True

        if model.rowCount(index):
            any_child_match = any(list(map(lambda child: self.recursively_search_columns(child, keywords),
                                           map(lambda row: model.index(row, index.column(), index),
                                               range(model.rowCount(index))))))
        else:
            any_child_match = False
        self.setExpanded(index, any_child_match)
        self.setRowHidden(index.row(), index.parent(), not any_child_match)
        return any_child_match

    def expand_self_and_collapse_children(self, index: QModelIndex):
        self.expand(index)
        model = self._model
        children = [model.createIndex(i, index.column(), index) for i in range(model.rowCount(index))]
        for child in children:
            self.collapse(child)

    def set_all_show_able(self, index: QModelIndex):
        model = self._model
        self.setRowHidden(index.row(), index.parent(), False)
        children = [model.index(row, index.column(), index) for row in range(model.rowCount(index))]
        for child in children:
            self.set_all_show_able(child)

    def show_children(self, index: QModelIndex):
        model = self._model
        children = [model.index(row, index.column(), index) for row in range(model.rowCount(index))]
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
            menu.addAction('Copy').triggered.connect(
                lambda: _copy_to_clipboard(self.model().data(index, Qt.ItemDataRole.EditRole)))
            menu.addAction('Show Children').triggered.connect(lambda: self.show_children(index))
            item = index.internalPointer()
            if isinstance(item, JsonModelItem):
                menu.addAction("Copy JSON Value").triggered.connect(lambda: _copy_to_clipboard(item.value))
                menu.addAction("Show Value As New Frame").triggered.connect(
                    lambda: _show_value_as_new_frame(item.key, item.value))
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
            frame.setWindowTitle(f'响应体: key={json_key}')
            frame.setFixedSize(800, 600)
            frame.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            frame.show()

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(_popup_item_menu)


class JsonDataFrame(QFrame):
    def __init__(self, data: Any, parent: Optional[QWidget] = None):
        super().__init__(parent)

        from .req_resp_json_frame_uic import Ui_Frame
        self.ui = Ui_Frame()
        self.ui.setupUi(self)
        tree_view = self.ui.json_tree_view
        tree_view.update_data(data)
        tree_view.header().sectionResized.connect(self.resize_search_widgets)
        tree_view.header().geometriesChanged.connect(self.resize_search_widgets)

        tree_view.expandAll()
        tree_view.resizeColumnToContents(0)

    def resize_search_widgets(self, *_):
        tree_view = self.ui.json_tree_view
        layout: QBoxLayout = self.ui.search_edits_area_widget.layout()
        for column in range(tree_view.model().columnCount()):
            layout.setStretch(column, tree_view.columnWidth(column))

    @Slot(str)
    def search(self, *_):
        tree_view = self.ui.json_tree_view
        model: JsonItemModel = tree_view.model()
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            tree_view.recursively_search_columns(index, [self.ui.key_search_edit.text(),
                                                         self.ui.value_search_edit.text()])


def main():
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication()
    frame = RequestManagerFrame()
    frame.show()
    sys.exit(app.exec())
