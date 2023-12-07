import enum
import socket
from datetime import datetime
from typing import Optional, Any
from urllib import parse as url_parse
from urllib.parse import urlparse

import requests
from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, Slot
from PySide6.QtWidgets import QFrame, QWidget, QTableView
from requests import Response, PreparedRequest


def _init_tab_widget_layout(tab_widget):
    tab_widget.setCurrentIndex(0)
    for idx in range(tab_widget.count()):
        widget = tab_widget.widget(idx)
        if isinstance(widget, QWidget) and widget.layout():
            widget.layout().setContentsMargins(0, 0, 0, 0)
            widget.layout().setSpacing(0)


class ReqRespFrame(QFrame):
    _req: PreparedRequest

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        from .req_resp_frame_uic import Ui_ReqRespFrame
        self.ui = Ui_ReqRespFrame()
        self.ui.setupUi(self)
        _init_tab_widget_layout(self.ui.main_tab_widget)

    def update_request(self, req: PreparedRequest):
        self._req = req
        self.update_url_area(req)
        self.ui.basic_info_table_view.update_request(req)
        queries = url_parse.parse_qs(url_parse.urlparse(req.url).query)
        url_params = {k: v[0] if len(v) == 1 else v for k, v in queries.items()}
        self.ui.req_url_params_frame.update_params(url_params)
        self.ui.req_headers_frame.update_headers(req.headers)
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
        self.ui.resp_headers_frame.update_headers(resp.headers)

    @property
    def request(self):
        return self._req  # todo

    @Slot()
    def send_request(self):
        req = self.request
        self.ui.basic_info_table_view.update_req_start_time(datetime.now())
        response = requests.request(req.method, req.url, headers=req.headers, data=req.body)
        self.ui.basic_info_table_view.update_req_end_time(datetime.now())
        self.update_response(response)


class BasicInfoTableView(QTableView):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._model = BasicInfoItemModel(self)
        self.setModel(self._model)
        self._model.dataChanged.connect(lambda *args: self.resizeColumnsToContents())

    def update_request(self, req: PreparedRequest):
        self._model.update_request(req)

    def update_response(self, resp: Response):
        self._model.update_response(resp)

    def update_req_start_time(self, req_start_time: datetime):
        self._model.update_req_start_time(req_start_time)

    def update_req_end_time(self, req_end_time: datetime):
        self._model.update_req_end_time(req_end_time)


class BasicInfoItemModel(QAbstractItemModel):
    class Label(enum.StrEnum):
        STATUS_CODE = '状态码'
        STATUS_INFO = '状态信息'
        START_TIME = '请求开始时间'
        END_TIME = '请求结束时间'
        RESPONSE_TIME = '响应时间'
        SERVER = '服务器'
        SERVER_IP = '服务器IP'
        SERVER_PORT = '服务器端口'

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.value_dict = dict[str, str]()

    def update_request(self, req: PreparedRequest):
        self.value_dict.clear()
        parsed_url = urlparse(req.url)
        self.value_dict[self.Label.SERVER] = parsed_url.hostname
        self.value_dict[self.Label.SERVER_IP] = socket.gethostbyname(parsed_url.hostname)
        self.value_dict[self.Label.SERVER_PORT] = str(parsed_url.port)
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, 1))

    def update_req_start_time(self, req_start_time: datetime):
        self.value_dict[self.Label.START_TIME] = str(req_start_time)
        if self.Label.END_TIME in self.value_dict:
            del self.value_dict[self.Label.END_TIME]
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, 1))

    def update_req_end_time(self, req_end_time: datetime):
        self.value_dict[self.Label.END_TIME] = str(req_end_time)
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, 1))

    def update_response(self, resp: Response):
        self.value_dict[self.Label.STATUS_CODE] = str(resp.status_code)
        self.value_dict[self.Label.STATUS_INFO] = str(resp.reason)
        self.value_dict[self.Label.RESPONSE_TIME] = str(resp.elapsed)
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, 1))

    def rowCount(self, parent: QModelIndex = None) -> int:
        return len(self.Label)

    def columnCount(self, parent: QModelIndex = None) -> int:
        return 2

    def data(self, index: QModelIndex, role: int = -1) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and index.isValid():
            label = list(self.Label)[index.row()]
            if index.column() == 0:
                return label
            elif index.column() == 1:
                return self.value_dict.get(label)
        return None

    def index(self, row: int, column: int, parent: QModelIndex = None) -> QModelIndex:
        return self.createIndex(row, column)

    def parent(self, child: QModelIndex = None) -> QModelIndex:
        return QModelIndex()


class ReqRespHeadersFrame(QFrame):

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        from .req_resp_headers_frame_uic import Ui_Frame
        self.ui = Ui_Frame()
        self.ui.setupUi(self)
        self.ui.headers_table_view.horizontalHeader().sectionResized.connect(self.resize_search_widgets)
        self.ui.headers_table_view.horizontalHeader().geometriesChanged.connect(self.resize_search_widgets)

    def update_headers(self, headers):
        self.ui.headers_table_view.update_headers(headers)

    def resize_search_widgets(self, *_):
        table_view = self.ui.headers_table_view
        self.ui.search_edits_area_widget.setFixedWidth(table_view.horizontalHeader().width())
        self.ui.key_search_input.setFixedWidth(table_view.columnWidth(0))
        self.ui.value_search_input.setFixedWidth(table_view.columnWidth(1))


class HeadersTableView(QTableView):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._model = HeadersTableModelItem(dict(), self)
        self.setModel(self._model)
        self._model.dataChanged.connect(lambda *args: self.resizeColumnsToContents())

    def update_headers(self, headers: dict):
        self._model.update_headers(headers)


class HeadersTableModelItem(QAbstractItemModel):
    def __init__(self, headers: dict, parent: QWidget):
        super().__init__(parent)
        self.headers = headers

    def update_headers(self, headers):
        self.headers.update(headers)
        self.layoutChanged.emit()

    def rowCount(self, parent: QModelIndex = None) -> int:
        return len(self.headers)

    def columnCount(self, parent: QModelIndex = None) -> int:
        return 2

    def data(self, index: QModelIndex, role: int = -1) -> Any:
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole) and index.isValid():
            key = self._header_key_at(index)
            if index.column() == 0:
                return key
            elif index.column() == 1:
                return self.headers[key]
        return None

    def _header_key_at(self, index):
        key_list = list(self.headers.keys())
        key_list.sort()
        key = key_list[index.row()]
        return key

    def setData(self, index: QModelIndex, value: Any, role: int = -1) -> bool:
        if role == Qt.ItemDataRole.EditRole and index.isValid():
            key = self._header_key_at(index)
            if index.column() == 0:
                self.headers[value] = self.headers.pop(key)
            elif index.column() == 1:
                self.headers[key] = value
            return True
        return False

    def index(self, row: int, column: int, parent: QModelIndex = None) -> QModelIndex:
        return self.createIndex(row, column)

    def parent(self, child: QModelIndex = None) -> QModelIndex:
        return QModelIndex()

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = ...) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return ('键', '值')[section]
        return None


class UrlParamsFrame(QFrame):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        from .req_resp_url_params_frame_uic import Ui_Frame
        self.ui = Ui_Frame()
        self.ui.setupUi(self)
        self.ui.url_params_table_view.horizontalHeader().geometriesChanged.connect(self.resize_search_widgets)
        self.ui.url_params_table_view.horizontalHeader().sectionResized.connect(self.resize_search_widgets)

    def resize_search_widgets(self, *_):
        table_view = self.ui.url_params_table_view
        self.ui.key_search_edit.parent().setFixedWidth(table_view.columnWidth(0) + table_view.columnWidth(1))
        self.ui.search_edits_area_widget.setFixedWidth(table_view.horizontalHeader().width())
        self.ui.key_search_edit.setFixedWidth(table_view.columnWidth(0))
        self.ui.value_search_edit.setFixedWidth(table_view.columnWidth(1))

    def update_params(self, params: dict):
        self.ui.url_params_table_view.update_params(params)

    def params_dict(self) -> dict:
        return self.ui.url_params_table_view.params_dict()


class UrlParamsTableView(QTableView):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._model = UrlParamsTableModelItem(dict(), self)
        self.setModel(self._model)
        self._model.dataChanged.connect(lambda *args: self.resizeColumnsToContents())

    def update_params(self, params: dict):
        self._model.update_params(params)

    def params_dict(self) -> dict:
        return self._model.params


class UrlParamsTableModelItem(QAbstractItemModel):
    ITEM_VALUE_TYPE_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, params: dict, parent: QWidget):
        super().__init__(parent)
        self.params = params

    def update_params(self, params: dict):
        self.params.update(params)
        self.layoutChanged.emit()

    def rowCount(self, parent: QModelIndex = None) -> int:
        return len(self.params)

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
            value = self.params[key]
            if isinstance(value, list) and len(value) == 1:
                value = value[0]
            if role == Qt.ItemDataRole.DisplayRole:
                return str(value)
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
        key_list = list(self.params.keys())
        key_list.sort()
        key = key_list[index.row()]
        return key

    def setData(self, index: QModelIndex, value: Any, role: int = -1) -> bool:
        if role == Qt.ItemDataRole.EditRole and index.isValid():
            key = self._param_key_at(index)
            if index.column() == 0:
                self.params[value] = self.params.pop(key)
            elif index.column() == 1:
                self.params[key] = value
            else:
                return False
            self.dataChanged.emit(index, index)
            return True
        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        return super().flags(index) | Qt.ItemFlag.ItemIsEditable

    def index(self, row: int, column: int, parent: QModelIndex = None) -> QModelIndex:
        return self.createIndex(row, column)

    def parent(self, child: QModelIndex = None) -> QModelIndex:
        return QModelIndex()


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
        _init_tab_widget_layout(self.ui.req_body_tab_widget)

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


class UrlParamsBodyFrame(UrlParamsFrame):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

    def __update_body__(self, data):
        params_dict = {k: v[0] if len(v) == 0 else v for k, v in url_parse.parse_qs(data).items()}
        super().update_params(params_dict)

    def __body_data__(self) -> Any:
        return super().params_dict()


def main():
    import sys
    import os
    from PySide6.QtWidgets import QApplication
    from my_dev_tools.my_request.curl import parse_curl

    app = QApplication()
    with open(os.path.expanduser('~/Downloads/curl.sh')) as f:
        command = f.read()

    req = parse_curl(command)

    frame = ReqRespFrame()
    frame.update_request(req.prepare())
    frame.setFixedSize(800, 600)
    frame.show()
    sys.exit(app.exec())
