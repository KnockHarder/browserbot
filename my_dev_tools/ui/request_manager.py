import enum
import json
from abc import abstractmethod, ABC
from typing import Optional, Any
from urllib.parse import urlparse, ParseResult

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtWidgets import QFrame, QWidget, QHBoxLayout, QTreeWidget, QTreeView
from requests import Request, Response


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
    def __init__(self, req: Request, *, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.req = req
        self._model = RequestItemModel(self, req)
        self.setModel(self._model)
        self.setExpandsOnDoubleClick(True)
        self.expandAll()


class ConstRows:
    class RootRow(enum.IntEnum):
        URL = 0
        METHOD = 1
        DOMAIN = 2
        PATH = 3
        UID = 4
        DID = 5
        REQUEST = 6
        RESPONSE = 7

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
    def child_sub_row_count(self, child: QModelIndex) -> int:
        pass

    def parent_index(self) -> (int, int, Optional["AbstractRequestItem"]):
        return -1, -1, None

    def child_item(self, row: int, column: int, parent: QModelIndex) -> Optional["AbstractRequestItem"]:
        return None


class ConstRequestItems:
    @staticmethod
    def _body_len(obj):
        return len(obj) if isinstance(obj, (dict, list)) else 1

    @staticmethod
    def _parse_req_data(req: Request):
        if isinstance(req.data, str):
            try:
                return json.loads(req.data)
            except Exception as e:
                print(e)
        return req.data

    @staticmethod
    def _parse_resp_data(resp: Response):
        try:
            return json.loads(resp.content)
        except Exception as e:
            print(e)
        return resp.content

    class TopLevelItem(AbstractRequestItem):
        def __init__(self, req: Request, resp: Response):
            self.req = req
            self.resp = resp
            self.text_data_dict = {
                ConstRows.RootRow.URL: ('URL', self.req.url),
                ConstRows.RootRow.METHOD: ('请求方式', self.req.method),
                ConstRows.RootRow.DOMAIN: ('域名', self.url.netloc),
                ConstRows.RootRow.PATH: ('相对路径', self.url.path),
                ConstRows.RootRow.UID: ('用户ID', self.req.params.get('ud')),
                ConstRows.RootRow.DID: ('设备ID', self.req.params.get('did')),
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

        @property
        def url(self) -> ParseResult:
            return urlparse(self.req.url)

        def child_sub_row_count(self, child: QModelIndex) -> int:
            if child.row() == ConstRows.RootRow.REQUEST:
                return len(ConstRows.RequestRow)
            elif child.row() == ConstRows.RootRow.RESPONSE:
                return len(ConstRows.ResponseRow)
            return 0

        def child_item(self, _, __, parent: QModelIndex) -> Optional[AbstractRequestItem]:
            if parent.row() == ConstRows.RootRow.REQUEST:
                return ConstRequestItems.RequestItem(self.req, self.resp)
            elif parent.row() == ConstRows.RootRow.RESPONSE:
                return ConstRequestItems.ResponseItem(self.req, self.resp)
            return None

    class RequestItem(AbstractRequestItem):
        def __init__(self, req: Request, resp: Response):
            self.req = req
            self.resp = resp

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

        def child_sub_row_count(self, child: QModelIndex) -> int:
            if child.row() == ConstRows.RequestRow.HEADER:
                return len(self.req.headers)
            elif child.row() == ConstRows.RequestRow.PARAMS:
                return len(self.req.params)
            elif child.row() == ConstRows.RequestRow.BODY:
                return ConstRequestItems._body_len(ConstRequestItems._parse_req_data(self.req))
            return 0

        def parent_index(self) -> (int, int, Optional["AbstractRequestItem"]):
            return ConstRows.RootRow.REQUEST, 0, ConstRequestItems.TopLevelItem(self.req, self.resp)

        def child_item(self, _, __, parent: QModelIndex) -> Optional["AbstractRequestItem"]:
            if parent.row() == ConstRows.RequestRow.HEADER:
                return ConstRequestItems.RequestHeaderItem(self.req, self.resp)
            elif parent.row() == ConstRows.RequestRow.PARAMS:
                return ConstRequestItems.RequestItem(self.req, self.resp)
            elif parent.row() == ConstRows.RequestRow.BODY:
                return ConstRequestItems.RequestBodyItem(self.req, self.resp)
            return None

    class ResponseItem(AbstractRequestItem):
        def __init__(self, req: Request, resp: Response):
            self.req = req
            self.resp = resp

        def data(self, index: QModelIndex, role=-1) -> Any:
            if role != Qt.ItemDataRole.DisplayRole:
                return None
            if index.row() == ConstRows.ResponseRow.HEADER:
                return ('响应头', '')[index.column()]
            elif index.row() == ConstRows.ResponseRow.BODY:
                return ('响应体', '')[index.column()]
            return None

        def child_sub_row_count(self, child: QModelIndex) -> int:
            if child.row() == ConstRows.ResponseRow.HEADER:
                return len(self.resp.headers)
            elif child.row() == ConstRows.ResponseRow.BODY:
                return ConstRequestItems._body_len(ConstRequestItems._parse_resp_data(self.resp))
            return 0

        def parent_index(self) -> (int, int, Optional["AbstractRequestItem"]):
            return ConstRows.RootRow.RESPONSE, 0, ConstRequestItems.TopLevelItem(self.req, self.resp)

        def child_item(self, _, __, parent: QModelIndex) -> Optional["AbstractRequestItem"]:
            if parent.row() == ConstRows.ResponseRow.HEADER:
                return ConstRequestItems.ResponseHeaderItem(self.req, self.resp)
            elif parent.row() == ConstRows.ResponseRow.BODY:
                return ConstRequestItems.ResponseBodyItem(self.req, self.resp)
            return None

    class RequestHeaderItem(AbstractRequestItem):
        def __init__(self, req: Request, resp: Response):
            self.req = req
            self.resp = resp

        def data(self, index: QModelIndex, role=-1) -> Any:
            if role != Qt.ItemDataRole.DisplayRole:
                return None
            if index.column() == 0:
                return list(self.req.headers.keys())[index.row()]
            elif index.column() == 1:
                return list(self.req.headers.values())[index.row()]
            return None

        def child_sub_row_count(self, child: QModelIndex) -> int:
            return 0

        def parent_index(self) -> (int, int, Optional["AbstractRequestItem"]):
            return ConstRows.RequestRow.HEADER, 0, ConstRequestItems.RequestItem(self.req, self.resp)

    class RequestParamsItem(AbstractRequestItem):
        def __init__(self, req: Request, resp: Response):
            self.req = req
            self.resp = resp

        def data(self, index: QModelIndex, role=-1) -> Any:
            if role != Qt.ItemDataRole.DisplayRole:
                return None
            if index.column() == 0:
                return list(self.req.params.keys())[index.row()]
            elif index.column() == 1:
                return list(self.req.params.values())[index.row()]
            return None

        def child_sub_row_count(self, child: QModelIndex) -> int:
            return 0

        def parent_index(self) -> (int, int, Optional["AbstractRequestItem"]):
            return ConstRows.RequestRow.PARAMS, 0, ConstRequestItems.RequestItem(self.req, self.resp)

    class RequestBodyItem(AbstractRequestItem):
        def __init__(self, req: Request, resp: Response):
            self.req = req
            self.resp = resp

        def data(self, index: QModelIndex, role=-1) -> Any:
            if role != Qt.ItemDataRole.DisplayRole:
                return None
            data = ConstRequestItems._parse_req_data(self.req)
            if isinstance(data, dict):
                if index.column() == 0:
                    return list(data.keys())[index.row()]
                elif index.column() == 1:
                    return str(list(data.values())[index.row()])  # todo
            elif isinstance(data, list):
                return (f'[{index.row()}]', data[index.row()])[index.column()]
            return None

        def child_sub_row_count(self, child: QModelIndex) -> int:
            return 0

        def parent_index(self) -> (int, int, Optional["AbstractRequestItem"]):
            return ConstRows.RequestRow.BODY, 0, ConstRequestItems.RequestItem(self.req, self.resp)

    class ResponseHeaderItem(AbstractRequestItem):
        def __init__(self, req: Request, resp: Response):
            self.req = req
            self.resp = resp

        def data(self, index: QModelIndex, role=-1) -> Any:
            if role != Qt.ItemDataRole.DisplayRole:
                return None
            if index.column() == 0:
                return list(self.resp.headers.keys())[index.row()]
            elif index.column() == 1:
                return list(self.resp.headers.values())[index.row()]
            return None

        def child_sub_row_count(self, child: QModelIndex) -> int:
            return 0

        def parent_index(self) -> (int, int, Optional["AbstractRequestItem"]):
            return ConstRows.ResponseRow.HEADER, 0, ConstRequestItems.ResponseItem(self.req, self.resp)

    class ResponseBodyItem(AbstractRequestItem):
        def __init__(self, req: Request, resp: Response):
            self.req = req
            self.resp = resp

        def data(self, index: QModelIndex, role=-1) -> Any:
            if role != Qt.ItemDataRole.DisplayRole:
                return None
            data = ConstRequestItems._parse_resp_data(self.resp)
            if isinstance(data, dict):
                if index.column() == 0:
                    return list(data.keys())[index.row()]
                elif index.column() == 1:
                    return str(list(data.values())[index.row()])
            elif isinstance(data, list):
                return (f'[{index.row()}]', data[index.row()])[index.column()]
            return None

        def child_sub_row_count(self, child: QModelIndex) -> int:
            return 0

        def parent_index(self) -> (int, int, Optional["AbstractRequestItem"]):
            return ConstRows.ResponseRow.BODY, 0, ConstRequestItems.ResponseItem(self.req, self.resp)


class JsonLevelItem(AbstractRequestItem):
    def __init__(self, data: Any, parent_row: int, parent_item: AbstractRequestItem):
        self.data = data
        self.parent_row = parent_row
        self.parent_item = parent_item
        self.children = []

    def data(self, index: QModelIndex, role=-1) -> Any:
        if role in [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole]:
            return self.display_data(index)

    def display_data(self, index: QModelIndex) -> Any:
        data = self.row_data(index.row())
        if isinstance(data, tuple):
            k, v = data
            v = '' if isinstance(v, (list, dict)) or not v else str(v)
            return (k, v)[index.column()]
        if data:
            return (str(data), '')[index.column()]
        return None

    def row_data(self, row: int) -> Any:
        if isinstance(self.data, dict):
            key_list = sorted(list(self.data.keys()))
            return key_list[row], self.data[key_list[row]]
        elif isinstance(self.data, list):
            return self.data[row]
        return None

    def child_sub_row_count(self, child: QModelIndex) -> int:
        data = self.row_data(child.row())
        if isinstance(data, tuple):
            _, data = data
        if isinstance(data, (dict, list)):
            return len(data)
        return 0

    def parent_index(self) -> (int, int, Optional["AbstractRequestItem"]):
        return self.parent_row, 0, self.parent_item

    def child_item(self, row: int, column: int, parent: QModelIndex) -> Optional["AbstractRequestItem"]:
        # todo
        pass


class RequestItemModel(QAbstractItemModel):

    def __init__(self, view: RequestView, req: Request, resp=Response()):
        super().__init__(view)
        self.view = view
        self.req = req
        self.resp = resp
        const_items = [ConstRequestItems.TopLevelItem(self.req, self.resp),
                       ConstRequestItems.RequestItem(self.req, self.resp),
                       ConstRequestItems.ResponseItem(self.req, self.resp),
                       ConstRequestItems.RequestHeaderItem(self.req, self.resp),
                       ConstRequestItems.RequestParamsItem(self.req, self.resp),
                       ConstRequestItems.RequestBodyItem(self.req, self.resp),
                       ConstRequestItems.ResponseHeaderItem(self.req, self.resp),
                       ConstRequestItems.ResponseBodyItem(self.req, self.resp)]
        self._const_item_dict = {type(item): item for item in const_items}
        self.req_headers_item = JsonLevelItem(self.req.headers, ConstRows.RequestRow.HEADER,
                                              self._const_item_dict.get(ConstRequestItems.RequestHeaderItem))
        self.req_params_item = req.prepare().headers

    def columnCount(self, parent: QModelIndex = None) -> int:
        return 2

    def rowCount(self, parent: QModelIndex = None) -> int:
        if not parent.isValid():
            return len(ConstRows.RootRow)
        item = parent.internalPointer()
        if not isinstance(item, AbstractRequestItem):
            return 0
        return item.child_sub_row_count(parent)

    def index(self, row: int, column: int, parent: QModelIndex = None) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        if not parent.isValid():
            item = ConstRequestItems.TopLevelItem(self.req, self.resp)
        else:
            parent_item: AbstractRequestItem = parent.internalPointer()
            item = parent_item.child_item(row, column, parent)
        if item:
            item = self._const_item_dict.get(type(item))
        return self.createIndex(row, column, item)

    def parent(self, child: QModelIndex = None) -> QModelIndex:
        item = child.internalPointer()
        if not isinstance(item, AbstractRequestItem):
            return QModelIndex()
        row, col, parent_item = item.parent_index()
        if parent_item:
            parent_item = self._const_item_dict.get(type(parent_item))
        return self.createIndex(row, col, parent_item)

    def data(self, index: QModelIndex, role=-1) -> Any:
        item: AbstractRequestItem = index.internalPointer()
        return item.data(index, role) if item else None


def main():
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication()
    request = Request(method='POST', url='https://api.gotalk.to/api/v1/chat/ask', data='{"question": "你好"}')
    view = RequestView(request)
    view.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
