import enum
from abc import abstractmethod, ABC
from typing import Optional, Any
from urllib.parse import urlparse, ParseResult

import requests
from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtWidgets import QFrame, QWidget, QHBoxLayout, QTreeWidget, QTreeView
from requests import Request, Response

from ..my_request import parse_request_body, pase_response_body


class RequestFrame(QFrame):
    def __init__(self, req: Request, *, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.req = req
        self.setup_ui()

    def setup_ui(self):
        layout = self._setup_frame()
        layout.addWidget(self._setup_request_tree())

    def _setup_frame(self):
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setContentsMargins(*([0] * 4))
        layout = QHBoxLayout(self)
        self.setLayout(layout)
        return layout

    def _setup_request_tree(self):
        tree_widget = QTreeWidget(self)
        return tree_widget

    def _create_request_info_item(self):
        pass


class RequestView(QTreeView):
    def __init__(self, req: Request, *, parent: Optional[QWidget] = None, resp=Response()):
        super().__init__(parent)
        self.req = req
        self._model = RequestItemModel(self, req, resp)
        self.setModel(self._model)
        self.setExpandsOnDoubleClick(True)


class ConstRows:
    class RootRow(enum.IntEnum):
        METHOD = 0
        URL = 1
        DOMAIN = 2
        PATH = 3
        REQUEST = 4
        RESPONSE = 5

    class RequestRow(enum.IntEnum):
        HEADER = 0
        PARAMS = 1
        BODY = 2

    class ResponseRow(enum.IntEnum):
        HEADER = 0
        BODY = 1


class AbstractRequestItem(ABC):
    @abstractmethod
    def data(self, index: QModelIndex, role=-1) -> Any:
        pass

    @abstractmethod
    def row_count(self, item_idx: QModelIndex) -> int:
        pass

    def parent_index(self) -> (int, int, Optional["AbstractRequestItem"]):
        return -1, -1, None

    def child_item(self, row: int, column: int, parent: QModelIndex) -> Optional["AbstractRequestItem"]:
        return None


class ConstRequestItems:
    class TopLevelItem(AbstractRequestItem):
        text_data_dict: dict[int, tuple]

        def __init__(self, req: Request):
            self.update_request(req)
            self.child_item_dict = dict[int, AbstractRequestItem]()

        def update_request(self, req):
            parsed_url: ParseResult = urlparse(req.url)
            self.text_data_dict = {
                ConstRows.RootRow.METHOD: ('Method', req.method),
                ConstRows.RootRow.URL: ('URL', parsed_url.scheme + '://' + parsed_url.netloc + parsed_url.path),
                ConstRows.RootRow.DOMAIN: ('域名', parsed_url.netloc),
                ConstRows.RootRow.PATH: ('相对路径', parsed_url.path),
                ConstRows.RootRow.REQUEST: ('请求', ''),
                ConstRows.RootRow.RESPONSE: ('响应', '')
            }

        def data(self, index: QModelIndex, role=-1) -> Any:
            if role != Qt.ItemDataRole.DisplayRole:
                return None
            columns_text = self.text_data_dict.get(index.row())
            if len(columns_text) > index.column():
                return columns_text[index.column()]
            return None

        def row_count(self, item_idx: QModelIndex) -> int:
            if item_idx.row() == ConstRows.RootRow.REQUEST:
                return len(ConstRows.RequestRow)
            elif item_idx.row() == ConstRows.RootRow.RESPONSE:
                return len(ConstRows.ResponseRow)
            return 0

        def child_item(self, _, __, parent: QModelIndex) -> Optional[AbstractRequestItem]:
            return self.child_item_dict.get(parent.row())

    class RequestItem(AbstractRequestItem):
        _req_header_item: "LeveledDataItem"
        _req_params_item: "LeveledDataItem"
        _req_body_item: "LeveledDataItem"

        def __init__(self, req: Request, parent_item: AbstractRequestItem):
            self.parent_item = parent_item
            self.update_request(req)

        def update_request(self, req: Request):
            self._req_header_item = LeveledDataItem(ConstRows.RequestRow.HEADER, '$', req.headers,
                                                    ConstRows.RootRow.REQUEST, self)
            self._req_params_item = LeveledDataItem(ConstRows.RequestRow.PARAMS, '$', req.params,
                                                    ConstRows.RootRow.REQUEST, self)
            self._req_body_item = LeveledDataItem(ConstRows.RequestRow.BODY, '$', parse_request_body(req),
                                                  ConstRows.RootRow.REQUEST, self)

        def data(self, index: QModelIndex, role=-1) -> Any:
            if role != Qt.ItemDataRole.DisplayRole:
                return None
            if index.row() == ConstRows.RequestRow.HEADER:
                return ('请求头', '')[index.column()]
            elif index.row() == ConstRows.RequestRow.PARAMS:
                return ('请求参数', '')[index.column()]
            elif index.row() == ConstRows.RequestRow.BODY:
                return ('请求体', '')[index.column()]
            return None

        def row_count(self, item_idx: QModelIndex) -> int:
            if item_idx.row() == ConstRows.RequestRow.HEADER:
                return len(self._req_header_item.value)
            elif item_idx.row() == ConstRows.RequestRow.PARAMS:
                return len(self._req_params_item.value)
            elif item_idx.row() == ConstRows.RequestRow.BODY:
                body = self._req_body_item.value
                return len(body) if isinstance(body, (list, dict)) else 0
            return 0

        def parent_index(self) -> (int, int, Optional["AbstractRequestItem"]):
            return ConstRows.RootRow.REQUEST, 0, self.parent_item

        def child_item(self, row: int, column: int, parent: QModelIndex) -> Optional["AbstractRequestItem"]:
            if parent.row() == ConstRows.RequestRow.HEADER:
                return self._req_header_item.child_item(row, column, parent)
            elif parent.row() == ConstRows.RequestRow.PARAMS:
                return self._req_params_item.child_item(row, column, parent)
            elif parent.row() == ConstRows.RequestRow.BODY:
                return self._req_body_item.child_item(row, column, parent)
            return None

    class ResponseItem(AbstractRequestItem):
        _resp_header_item: "LeveledDataItem"
        _resp_body_item: "LeveledDataItem"

        def __init__(self, resp: Response, parent_item: AbstractRequestItem):
            self.parent_item = parent_item
            self.update_response(resp)

        def update_response(self, resp):
            self._resp_header_item = LeveledDataItem(ConstRows.ResponseRow.HEADER, '$', dict(resp.headers),
                                                     ConstRows.RootRow.RESPONSE, self)
            self._resp_body_item = LeveledDataItem(ConstRows.ResponseRow.BODY, '$', pase_response_body(resp),
                                                   ConstRows.RootRow.RESPONSE, self)

        def data(self, index: QModelIndex, role=-1) -> Any:
            if role != Qt.ItemDataRole.DisplayRole:
                return None
            if index.row() == ConstRows.ResponseRow.HEADER:
                return ('响应头', '')[index.column()]
            elif index.row() == ConstRows.ResponseRow.BODY:
                return ('响应体', '')[index.column()]
            return None

        def row_count(self, item_idx: QModelIndex) -> int:
            if item_idx.row() == ConstRows.ResponseRow.HEADER:
                return len(self._resp_header_item.value) if isinstance(self._resp_header_item.value, dict) else 0
            elif item_idx.row() == ConstRows.ResponseRow.BODY:
                body = self._resp_body_item.value
                return len(body) if isinstance(body, (list, dict)) else 0
            return 0

        def parent_index(self) -> (int, int, Optional["AbstractRequestItem"]):
            return ConstRows.RootRow.RESPONSE, 0, self.parent_item

        def child_item(self, row: int, column: int, parent: QModelIndex) -> Optional["AbstractRequestItem"]:
            if parent.row() == ConstRows.ResponseRow.HEADER:
                return self._resp_header_item.child_item(row, column, parent)
            elif parent.row() == ConstRows.ResponseRow.BODY:
                return self._resp_body_item.child_item(row, column, parent)
            return None


class LeveledDataItem(AbstractRequestItem):
    def __init__(self, row: int, key: str, value: Any, parent_row: int, parent_item: AbstractRequestItem):
        self.row = row
        self.key = key
        self.value = value
        self.parent_row = parent_row
        self.parent_item = parent_item
        self.children: list[LeveledDataItem] = [None] * len(value) if isinstance(value, (list, dict)) else []

    def data(self, index: QModelIndex, role=-1) -> Any:
        if role in [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole]:
            if isinstance(self.value, (list, dict)) or self.value is None:
                display_value = ''
            else:
                display_value = str(self.value)
            return (str(self.key), display_value)[index.column()]

    def row_count(self, item_idx: QModelIndex) -> int:
        return len(self.value) if isinstance(self.value, (list, dict)) else 0

    def parent_index(self) -> (int, int, Optional["AbstractRequestItem"]):
        return self.parent_row, 0, self.parent_item

    def child_item(self, row: int, column: int, parent: QModelIndex) -> Optional["AbstractRequestItem"]:
        if len(self.children) <= row:
            return None
        if self.children[row] is not None:
            return self.children[row]
        key, value = self.row_kv(row)
        self.children[row] = LeveledDataItem(row, key, value, self.row, self)
        return self.children[row]

    def row_kv(self, row: int) -> Optional[tuple]:
        if isinstance(self.value, dict):
            key_list = sorted(list(self.value.keys()))
            return key_list[row], self.value[key_list[row]]
        elif isinstance(self.value, list):
            return f'[{row}]', self.value[row]
        return None


class RequestItemModel(QAbstractItemModel):

    def __init__(self, view: RequestView, req: Request, resp: Response):
        super().__init__(view)
        self.view = view
        self.top_level_item = ConstRequestItems.TopLevelItem(req)
        self.request_item = ConstRequestItems.RequestItem(req, self.top_level_item)
        self.response_item = ConstRequestItems.ResponseItem(resp, self.top_level_item)
        self.top_level_item.child_item_dict = {
            ConstRows.RootRow.REQUEST.value: self.request_item,
            ConstRows.RootRow.RESPONSE.value: self.response_item
        }

    def update_request(self, req: Request):
        self.top_level_item.update_request(req)
        self.request_item.update_request(req)
        self.layoutChanged.emit()

    def update_response(self, resp: Response):
        self.response_item.update_response(resp)
        self.layoutChanged.emit()

    def columnCount(self, parent: QModelIndex = None) -> int:
        return 2

    def rowCount(self, parent: QModelIndex = None) -> int:
        if not parent:
            parent = QModelIndex()
        if not parent.isValid():
            return len(ConstRows.RootRow)
        parent_item = parent.internalPointer()
        if not isinstance(parent_item, AbstractRequestItem):
            return 0
        return parent_item.row_count(parent)

    def index(self, row: int, column: int, parent: QModelIndex = None) -> QModelIndex:
        if not parent:
            parent = QModelIndex()
        if not parent.isValid():
            item = self.top_level_item
        else:
            parent_item: AbstractRequestItem = parent.internalPointer()
            item = parent_item.child_item(row, column, parent)
        return self.createIndex(row, column, item)

    def parent(self, child: QModelIndex = None) -> QModelIndex:
        item = child.internalPointer()
        if not isinstance(item, AbstractRequestItem):
            return QModelIndex()
        row, col, parent_item = item.parent_index()
        return self.createIndex(row, col, parent_item)

    def data(self, index: QModelIndex, role=-1) -> Any:
        item: AbstractRequestItem = index.internalPointer()
        return item.data(index, role) if item else None


def main():
    import sys
    import os
    from PySide6.QtWidgets import QApplication
    from my_dev_tools.my_request.curl import parse_curl

    app = QApplication()
    with open(os.path.expanduser('~/Downloads/curl.sh')) as f:
        command = f.read()

    req = parse_curl(command)

    view = RequestView(req)
    with requests.Session().send(req.prepare()) as resp:
        view.model().update_response(resp)
    for i in range(view.model().columnCount()):
        view.resizeColumnToContents(i)
    view.setFixedSize(600, 400)
    view.show()
    sys.exit(app.exec())
