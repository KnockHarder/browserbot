import enum
from abc import abstractmethod, ABC
from typing import Optional, Any
from urllib.parse import urlparse

import requests
from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtGui import QColor
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
        self._model = ReqRespItemModel(self, req, resp)
        self.setModel(self._model)
        self.setExpandsOnDoubleClick(True)


class AbstractModelItem(ABC):
    @abstractmethod
    def data(self, index: QModelIndex, role=-1) -> Any:
        pass

    @abstractmethod
    def row_count(self, item_idx: QModelIndex) -> int:
        pass

    def parent(self) -> (int, int, Optional["AbstractModelItem"]):
        return -1, -1, None

    def child_item(self, row: int, column: int, item_idx: QModelIndex) -> Optional["AbstractModelItem"]:
        return None


class ConstLevelModelItem(AbstractModelItem, ABC):
    @abstractmethod
    def same_level_row_count(self) -> int:
        pass

    @abstractmethod
    def index_for_child_item(self, item: "AbstractModelItem") -> (int, int):
        pass


class RootLevelModelItem(ConstLevelModelItem):
    class SubRow(enum.IntEnum):
        METHOD_AND_URL = 0
        REQUEST = 1
        RESPONSE = 2

    method: str
    url: str
    req_level_item: "RequestLevelModelItem"
    resp_level_item: "ResponseLevelModelItem"

    def __init__(self, req: Request):
        self.update_request(req)

    def update_request(self, req):
        self.method = str(req.method)
        parsed_url = urlparse(req.url)
        self.url = parsed_url.scheme + '://' + parsed_url.netloc + parsed_url.path

    def same_level_row_count(self) -> int:
        return len(RootLevelModelItem.SubRow)

    def data(self, index: QModelIndex, role=-1) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if index.row() == RootLevelModelItem.SubRow.METHOD_AND_URL:
            return (self.method, self.url)[index.column()]
        elif index.row() == RootLevelModelItem.SubRow.REQUEST and index.column() == 0:
            return '请求'
        elif index.row() == RootLevelModelItem.SubRow.RESPONSE and index.column() == 0:
            return '响应'
        return None

    def row_count(self, item_idx: QModelIndex) -> int:
        item = self.child_item(0, 0, item_idx)
        return item.same_level_row_count() if item else 0

    def child_item(self, _, __, item_idx: QModelIndex) -> Optional[ConstLevelModelItem]:
        if item_idx.row() == RootLevelModelItem.SubRow.REQUEST:
            return self.req_level_item
        elif item_idx.row() == RootLevelModelItem.SubRow.RESPONSE:
            return self.resp_level_item
        return None

    def index_for_child_item(self, item: "AbstractModelItem") -> (int, int):
        if item == self.req_level_item:
            return RootLevelModelItem.SubRow.REQUEST, 0
        elif item == self.resp_level_item:
            return RootLevelModelItem.SubRow.RESPONSE, 0
        return -1, -1


class RequestLevelModelItem(ConstLevelModelItem):
    class SubRow(enum.IntEnum):
        HEADER = 0
        PARAMS = 1
        BODY = 2

    _req_header_item: "DataModelItem"
    _req_params_item: "DataModelItem"
    _req_body_item: "DataModelItem"

    def __init__(self, req: Request, parent_item: ConstLevelModelItem):
        self.parent_item = parent_item
        self.update_request(req)

    def same_level_row_count(self) -> int:
        return len(RequestLevelModelItem.SubRow)

    def update_request(self, req: Request):
        self._req_header_item = DataModelItem(RequestLevelModelItem.SubRow.HEADER, '$', req.headers,
                                              -1, self)
        self._req_params_item = DataModelItem(RequestLevelModelItem.SubRow.PARAMS, '$', req.params,
                                              -1, self)
        self._req_body_item = DataModelItem(RequestLevelModelItem.SubRow.BODY, '$', parse_request_body(req),
                                            -1, self)

    def data(self, index: QModelIndex, role=-1) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if index.row() == RequestLevelModelItem.SubRow.HEADER:
            return ('请求头', '')[index.column()]
        elif index.row() == RequestLevelModelItem.SubRow.PARAMS:
            return ('请求参数', '')[index.column()]
        elif index.row() == RequestLevelModelItem.SubRow.BODY:
            return ('请求体', '')[index.column()]
        return None

    def row_count(self, item_idx: QModelIndex) -> int:
        if item_idx.row() == RequestLevelModelItem.SubRow.HEADER:
            return len(self._req_header_item.value)
        elif item_idx.row() == RequestLevelModelItem.SubRow.PARAMS:
            return len(self._req_params_item.value)
        elif item_idx.row() == RequestLevelModelItem.SubRow.BODY:
            body = self._req_body_item.value
            return len(body) if isinstance(body, (list, dict)) else 0
        return 0

    def parent(self) -> (int, int, Optional["AbstractModelItem"]):
        row, column = self.parent_item.index_for_child_item(self)
        return row, column, self.parent_item

    def child_item(self, row: int, column: int, item_idx: QModelIndex) -> Optional["AbstractModelItem"]:
        if item_idx.row() == RequestLevelModelItem.SubRow.HEADER:
            return self._req_header_item.child_item(row, column, item_idx)
        elif item_idx.row() == RequestLevelModelItem.SubRow.PARAMS:
            return self._req_params_item.child_item(row, column, item_idx)
        elif item_idx.row() == RequestLevelModelItem.SubRow.BODY:
            return self._req_body_item.child_item(row, column, item_idx)
        return None

    def index_for_child_item(self, item: "AbstractModelItem") -> (int, int):
        return -1, -1


class ResponseLevelModelItem(ConstLevelModelItem):
    class SubRow(enum.IntEnum):
        HEADER = 0
        BODY = 1

    _resp_header_item: "DataModelItem"
    _resp_body_item: "DataModelItem"

    def __init__(self, resp: Response, parent_item: ConstLevelModelItem):
        self.parent_item = parent_item
        self.update_response(resp)

    def same_level_row_count(self) -> int:
        return len(ResponseLevelModelItem.SubRow)

    def update_response(self, resp):
        self._resp_header_item = DataModelItem(ResponseLevelModelItem.SubRow.HEADER, '$', dict(resp.headers),
                                               -1, self)
        self._resp_body_item = DataModelItem(ResponseLevelModelItem.SubRow.BODY, '$', pase_response_body(resp),
                                             -1, self)

    def data(self, index: QModelIndex, role=-1) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if index.row() == ResponseLevelModelItem.SubRow.HEADER:
            return ('响应头', '')[index.column()]
        elif index.row() == ResponseLevelModelItem.SubRow.BODY:
            return ('响应体', '')[index.column()]
        return None

    def row_count(self, item_idx: QModelIndex) -> int:
        if item_idx.row() == ResponseLevelModelItem.SubRow.HEADER:
            return len(self._resp_header_item.value) if isinstance(self._resp_header_item.value, dict) else 0
        elif item_idx.row() == ResponseLevelModelItem.SubRow.BODY:
            body = self._resp_body_item.value
            return len(body) if isinstance(body, (list, dict)) else 0
        return 0

    def parent(self) -> (int, int, Optional["AbstractModelItem"]):
        row, column = self.parent_item.index_for_child_item(self)
        return row, column, self.parent_item

    def child_item(self, row: int, column: int, item_idx: QModelIndex) -> Optional["AbstractModelItem"]:
        if item_idx.row() == ResponseLevelModelItem.SubRow.HEADER:
            return self._resp_header_item.child_item(row, column, item_idx)
        elif item_idx.row() == ResponseLevelModelItem.SubRow.BODY:
            return self._resp_body_item.child_item(row, column, item_idx)
        return None

    def index_for_child_item(self, item: "AbstractModelItem") -> (int, int):
        return -1, -1


class DataModelItem(AbstractModelItem):
    def __init__(self, row: int, key: str, value: Any, parent_row: int, parent_item: AbstractModelItem):
        self.row = row
        self.key = key
        self.value = value
        self.parent_row = parent_row
        self.parent_item = parent_item
        self.children: list[DataModelItem] = [None] * len(value) if isinstance(value, (list, dict)) else []

    def data(self, index: QModelIndex, role=-1) -> Any:
        item_data = dict[int, Any]()
        if index.column() == 0:
            item_data.update({
                Qt.ItemDataRole.DisplayRole: str(self.key),
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
                    Qt.ItemDataRole.EditRole: self.value
                })
        return item_data.get(role)

    def row_count(self, item_idx: QModelIndex) -> int:
        return len(self.value) if isinstance(self.value, (list, dict)) else 0

    def parent(self) -> (int, int, Optional["AbstractModelItem"]):
        return self.parent_row, 0, self.parent_item

    def child_item(self, row: int, column: int, item_idx: QModelIndex) -> Optional["AbstractModelItem"]:
        if len(self.children) <= row:
            return None
        if self.children[row] is not None:
            return self.children[row]
        key, value = self.row_kv(row)
        self.children[row] = DataModelItem(row, key, value, self.row, self)
        return self.children[row]

    def row_kv(self, row: int) -> Optional[tuple]:
        if isinstance(self.value, dict):
            key_list = sorted(list(self.value.keys()))
            return key_list[row], self.value[key_list[row]]
        elif isinstance(self.value, list):
            return f'[{row}]', self.value[row]
        return None


class ReqRespItemModel(QAbstractItemModel):

    def __init__(self, view: RequestView, req: Request, resp: Response):
        super().__init__(view)
        self.view = view
        self.root_level_item = RootLevelModelItem(req)
        self.request_level_item = RequestLevelModelItem(req, self.root_level_item)
        self.response_level_item = ResponseLevelModelItem(resp, self.root_level_item)
        self.root_level_item.req_level_item = self.request_level_item
        self.root_level_item.resp_level_item = self.response_level_item

    def update_request(self, req: Request):
        self.root_level_item.update_request(req)
        self.request_level_item.update_request(req)
        self.layoutChanged.emit()

    def update_response(self, resp: Response):
        self.response_level_item.update_response(resp)
        self.layoutChanged.emit()

    def columnCount(self, parent: QModelIndex = None) -> int:
        return 2

    def rowCount(self, parent: QModelIndex = None) -> int:
        if not parent:
            parent = QModelIndex()
        if not parent.isValid():
            return self.root_level_item.same_level_row_count()
        parent_item = parent.internalPointer()
        if not isinstance(parent_item, AbstractModelItem):
            return 0
        return parent_item.row_count(parent)

    def index(self, row: int, column: int, parent: QModelIndex = None) -> QModelIndex:
        if not parent:
            parent = QModelIndex()
        if not parent.isValid():
            item = self.root_level_item
        else:
            parent_item: AbstractModelItem = parent.internalPointer()
            item = parent_item.child_item(row, column, parent)
        return self.createIndex(row, column, item)

    def parent(self, child: QModelIndex = None) -> QModelIndex:
        item = child.internalPointer()
        if not isinstance(item, AbstractModelItem):
            return QModelIndex()
        row, col, parent_item = item.parent()
        return self.createIndex(row, col, parent_item)

    def data(self, index: QModelIndex, role=-1) -> Any:
        item: AbstractModelItem = index.internalPointer()
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
