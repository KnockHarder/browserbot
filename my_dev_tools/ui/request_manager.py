import enum
import socket
from datetime import datetime
from typing import Optional, Any
from urllib.parse import urlparse

import requests
from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, Slot
from PySide6.QtWidgets import QFrame, QWidget
from requests import Request, Response


class ReqRespFrame(QFrame):
    _req: Request

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        from .req_resp_frame_uic import Ui_ReqRespFrame
        self.ui = Ui_ReqRespFrame()
        self.ui.setupUi(self)
        self.init_tab_widget()

        view = self.ui.basic_info_table_view
        model = BasicInfoItemModel(view)
        self.basic_info_view = view
        self.basic_model = model
        view.setModel(self.basic_model)
        model.dataChanged.connect(lambda *args: view.resizeColumnsToContents())

    def init_tab_widget(self):
        tab_widget = self.ui.main_tab_widget
        tab_widget.setCurrentIndex(0)
        for idx in range(tab_widget.count()):
            widget = tab_widget.widget(idx)
            if isinstance(widget, QWidget) and widget.layout():
                widget.layout().setContentsMargins(0, 0, 0, 0)
                widget.layout().setSpacing(0)

    def update_request(self, req: Request):
        self._req = req
        self.update_url_area(req)
        self.basic_model.update_request(req)
        self.ui.req_headers_frame.update_headers(req.headers)

    def update_url_area(self, req):
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
        self.basic_model.update_response(resp)
        self.ui.resp_headers_frame.update_headers(resp.headers)

    @property
    def request(self):
        return self._req  # todo

    @Slot()
    def send_request(self):
        prepared = self.request.prepare()
        self.basic_model.update_req_start_time(datetime.now())
        response = requests.request(prepared.method, prepared.url, headers=prepared.headers, data=prepared.body)
        self.basic_model.update_req_end_time(datetime.now())
        self.update_response(response)


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

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.value_dict = dict[str, str]()

    def update_request(self, req: Request):
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

        table_view = self.ui.headers_table_view
        headers_model = HeadersTableModelItem(dict(), table_view)
        self._headers_model = headers_model
        table_view.setModel(self._headers_model)
        headers_model.dataChanged.connect(self.resize_contents)
        headers_model.layoutChanged.connect(self.resize_contents)

    def update_headers(self, headers):
        self._headers_model.update_headers(headers)

    def resize_contents(self, *args):
        table_view = self.ui.headers_table_view
        table_view.resizeColumnsToContents()
        self.ui.key_search_input.setFixedWidth(table_view.columnWidth(0))
        self.ui.value_search_input.setFixedWidth(table_view.columnWidth(1))


class HeadersTableModelItem(QAbstractItemModel):
    def __init__(self, headers: dict, parent: Optional[QWidget] = None):
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
            key = list(self.headers.keys())[index.row()]
            if index.column() == 0:
                return key
            elif index.column() == 1:
                return self.headers[key]
        return None

    def setData(self, index: QModelIndex, value: Any, role: int = -1) -> bool:
        if role == Qt.ItemDataRole.EditRole and index.isValid():
            key = list(self.headers.keys())[index.row()]
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
    frame.update_request(req)
    frame.setFixedSize(800, 600)
    frame.show()
    sys.exit(app.exec())
