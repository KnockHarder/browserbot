import datetime
import json
import os
import pickle
import sys
import time
import uuid
from typing import Optional, Union, Any, Sequence

from PySide6.QtCore import Slot, Qt, QTimer, QModelIndex, QPersistentModelIndex, QAbstractItemModel, QEvent, \
    Signal, QRect, QSize, QMimeData
from PySide6.QtGui import QShortcut, QPalette, QBrush, QPaintEvent, QHoverEvent, QPainter, QTextDocument, QKeySequence, \
    QPixmap
from PySide6.QtWidgets import QFrame, QWidget, QFileDialog, QApplication, \
    QMenu, QAbstractItemView, QFormLayout, QLineEdit, QTableView, \
    QStyleOptionViewItem, QAbstractItemDelegate, QHBoxLayout, QPushButton, QStyle

import mywidgets.dialog as my_dialog
import url_manager_frame_rc
from browser import get_browser
from config import url_table_data_dir
from mywidgets import AccessibleTableUi


def read_tab_data_from_file(path: str):
    with open(path, 'r') as fp:
        return json.load(fp)


def main_data_file_path():
    return os.path.join(url_table_data_dir(), 'main.json')


def month_data_file_path():
    month_file = datetime.datetime.now().strftime("%Y_%m") + '.json'
    month_file = os.path.join(url_table_data_dir(), month_file)
    return month_file


class UrlData:
    def __init__(self, category: str, name: str, url: str):
        self.category = category
        self.name = name
        self.url = url

    @classmethod
    def from_dict(cls, data: dict) -> "UrlData":
        return cls(data.get('category'), data.get('name'), data.get('url'))

    def __repr__(self):
        return f'<UrlData[category={self.category}, name={self.name}, url={self.url}]>'


class UrlManagerTabFrame(QFrame):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.is_saving = False
        from ui.url_manager_tab_uic import Ui_Frame
        self.ui = Ui_Frame()
        self.ui.setupUi(self)
        tab_widget = self.ui.tabWidget
        tab_widget.tabBarDoubleClicked.connect(self.rename_tab)
        tab_widget.tabCloseRequested.connect(self.archive_tab)

        self.load_main_data()
        self.schedule_to_save_data()
        self.bind_keys()

    def load_main_data(self):
        path = main_data_file_path()
        if not os.path.exists(path):
            return
        tabs = read_tab_data_from_file(path)
        for data in tabs:
            url_list = list(map(lambda x: UrlData.from_dict(x), data['urls']))
            self.create_tab_from_data(data['tabName'], url_list, data.get('id'))

    @Slot()
    def add_tab(self):
        def create_new_tab(name: str):
            index = self.create_tab_from_data(name)
            self.ui.tabWidget.setCurrentIndex(index)

        my_dialog.show_input_dialog('新增标签页', '标签页名称', self,
                                    text_value_select_callback=create_new_tab)

    def create_tab_from_data(self, tab_name: str, urls: list = None, table_id: str = None):
        tab_widget = self.ui.tabWidget
        table = UrlTableView(tab_widget, table_id, urls)
        tab_widget.addTab(table, tab_name)
        return tab_widget.count() - 1

    @Slot()
    def add_tab_from_file(self):
        def _select_tabs_in_file(path: str):
            tabs = read_tab_data_from_file(path)
            my_dialog.show_items_select_dialog('选取加载TAB页', [data['tabName'] for data in tabs], self,
                                               text_value_selected_func=lambda name: _load_tab_selected(name, tabs))

        def _load_tab_selected(tab_name: str, tabs: list[dict]):
            data = next(filter(lambda x: x['tabName'] == tab_name, tabs), None)
            url_list = list(map(lambda x: UrlData.from_dict(x), data['urls']))
            idx = self.create_tab_from_data(tab_name, url_list, data.get('id'))
            self.ui.tabWidget.setCurrentIndex(idx)

        dialog = QFileDialog(self, '加载链接表', url_table_data_dir(), 'JSON Files(*.json)')
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.fileSelected.connect(_select_tabs_in_file)
        dialog.open()

    def archive_tab(self, index: int):
        tab_widget = self.ui.tabWidget

        tab_name = tab_widget.tabText(index)
        table: UrlTableView = tab_widget.widget(index)
        month_file = month_data_file_path()
        file_tabs = read_tab_data_from_file(month_file) if os.path.exists(month_file) else []
        file_tabs = list(filter(lambda x: x.get('id') != table.id and x['tabName'] != tab_name, file_tabs))
        file_tabs.append({
            "id": table.id,
            "tabName": tab_name,
            "urls": table.get_url_datas()
        })
        with open(month_file, 'w') as fp:
            json.dump(file_tabs, fp, ensure_ascii=False, indent=2)
        tab_widget.removeTab(index)

    def rename_tab(self, index: int):
        def _rename_tab(name: str):
            self.ui.tabWidget.setTabText(index, name)

        if index >= 0:
            my_dialog.show_input_dialog('重命名标签页', '标签页名称', self,
                                        text_value=self.ui.tabWidget.tabText(index),
                                        text_value_select_callback=_rename_tab)
        else:
            self.add_tab()

    def save_to_json(self):
        while self.is_saving:
            print('Waiting for saving')
            time.sleep(1)
        self.is_saving = True
        try:
            tab_widget = self.ui.tabWidget
            all_data = list()
            for idx in range(tab_widget.count()):
                table: UrlTableView = tab_widget.widget(idx)
                all_data.append({
                    "id": table.id,
                    "tabName": tab_widget.tabText(idx),
                    "urls": table.get_url_datas()
                })
            with open(main_data_file_path(), 'w') as fp:
                json.dump(all_data, fp, ensure_ascii=False, indent=2)
        finally:
            self.is_saving = False

    def schedule_to_save_data(self):
        timer = QTimer(self)
        timer.timeout.connect(self.save_to_json)
        timer.start(5000)

    def bind_keys(self):
        tab_widget = self.ui.tabWidget

        def switch_tab(idx: int):
            if idx >= tab_widget.count():
                return
            tab_widget.setCurrentIndex(idx)

        for i in range(0, 9):
            num_key = (i + 1) % 10
            QShortcut(f'Alt+{num_key}', self, lambda _i=i: switch_tab(_i))


class UrlTableView(QTableView):
    menu: QMenu

    def __init__(self, parent: Optional[QWidget] = None, table_id: str = None, url_list: list[UrlData] = None):
        super().__init__(parent)
        self.browser = get_browser()
        self.id = table_id if table_id else str(uuid.uuid1())

        self.item_model = UrlTableItemModel(self, url_list)
        self.setModel(self.item_model)
        self.accessible_ui = AccessibleTableUi(self, self.item_model)
        self.accessible_ui.setup_ui()
        self.setStyleSheet('QTableView::item:selected {background-color: #6666ffff}')

        self.setItemDelegateForColumn(UrlTableItemModel.URL_COLUMN, UrlColumnItemDelegate(self))
        self.setItemDelegateForColumn(UrlTableItemModel.OPERATOR_COLUMN, OperatorColumnItemDelegate(self))
        self.resizeColumnsToContents()

        self.setEditTriggers(QAbstractItemView.EditTrigger.EditKeyPressed)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.init_menu()
        self.doubleClicked.connect(self.go_cell_url)

    def paintEvent(self, e: QPaintEvent) -> None:
        super().paintEvent(e)
        self.accessible_ui.update_add_row_buttons()

    def event(self, e: QEvent) -> bool:
        result = super().event(e)
        if isinstance(e, QHoverEvent):
            self.accessible_ui.show_add_row_button_hovered(e)
        return result

    def delete_row_by_click(self):
        widget = self.sender()
        for row in range(self.model().rowCount()):
            index = self.model().index(row, UrlTableItemModel.OPERATOR_COLUMN)
            if widget == self.indexWidget(index):
                self.model().removeRow(row)
                return

    def go_cell_url(self, index: QModelIndex):
        url = index.data(UrlTableItemModel.LINK_ITEM_ROLE)
        if url:
            self.browser.to_page_or_open_url(url, activate=True)

    def rowsAboutToBeRemoved(self, parent: Union[QModelIndex, QPersistentModelIndex], start: int, end: int) -> None:
        for row in range(start, end + 1):
            for col in range(self.model().rowCount()):
                index = self.model().index(row, col, parent)
                widget = self.indexWidget(index)
                if widget:
                    widget.deleteLater()

    def get_url_datas(self) -> list:
        return list(map(lambda data: vars(data),
                        map(lambda i: self.item_model.url_list[i],
                            map(lambda i: self.verticalHeader().logicalIndex(i), range(self.model().rowCount())))))

    def init_menu(self):
        menu = self.menu = QMenu(self)
        menu.addAction('Open Links Selected').triggered.connect(self.open_selected_urls)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda position: menu.exec(
            self.viewport().mapToGlobal(position)))

    def open_selected_urls(self):
        indexes = self.selectedIndexes()
        for idx in indexes:
            url = idx.data(UrlTableItemModel.LINK_ITEM_ROLE)
            if url:
                self.browser.to_page_or_open_url(url, activate=True)


class UrlTableItemModel(QAbstractItemModel):
    CATEGORY_COLUMN = 0
    URL_COLUMN = 1
    OPERATOR_COLUMN = 2
    LINK_ITEM_ROLE = Qt.ItemDataRole.UserRole
    URL_DATA_LIST_TYPE = 'application/x-url-data-index-list'
    URL_FOREGROUND = QBrush(QApplication.palette().color(QPalette.ColorRole.Link))

    def __init__(self, view: QTableView, url_list: list[UrlData]):
        super().__init__(view)

        self.view = view
        self.url_list = list(url_list) if url_list else []

    def columnCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = None) -> int:
        return 3

    def rowCount(self, parent: Union[QModelIndex, QPersistentModelIndex] = None) -> int:
        return len(self.url_list)

    def index(self, row: int, column: int, parent: Union[QModelIndex, QPersistentModelIndex] = None) -> QModelIndex:
        return self.createIndex(row, column)

    def parent(self, child: Union[QModelIndex, QPersistentModelIndex] = None) -> QModelIndex:
        return QModelIndex()

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = 0) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section == self.CATEGORY_COLUMN:
                return '分类'
            elif section == self.URL_COLUMN:
                return '链接'
            elif section == self.OPERATOR_COLUMN:
                return '操作'
        if orientation == Qt.Orientation.Vertical and role == Qt.ItemDataRole.DisplayRole:
            return str(self.view.verticalHeader().visualIndex(section) + 1)
        return None

    def data(self, index: Union[QModelIndex, QPersistentModelIndex], role: int = -1) -> Any:
        url_data = self.url_list[index.row()]
        url_data_attr = self.get_url_data_attr(index.column(), role)
        return url_data.__getattribute__(url_data_attr) if url_data_attr else None

    def get_url_data_attr(self, column: int, role: int) -> str:
        if column == self.CATEGORY_COLUMN:
            return {
                Qt.ItemDataRole.DisplayRole.value: 'category',
                Qt.ItemDataRole.EditRole.value: 'category'
            }.get(role)
        elif column == self.URL_COLUMN:
            return {
                Qt.ItemDataRole.DisplayRole.value: 'name',
                self.LINK_ITEM_ROLE: 'url'
            }.get(role)
        else:
            return ''

    def flags(self, index: Union[QModelIndex, QPersistentModelIndex]) -> Qt.ItemFlag:
        flag = super().flags(index)
        if index.column() in [self.CATEGORY_COLUMN, self.URL_COLUMN]:
            flag |= Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled
        return flag

    def setData(self, index: Union[QModelIndex, QPersistentModelIndex], value: Any, role: int = 0) -> bool:
        url_data_attr = self.get_url_data_attr(index.column(), role)
        if url_data_attr:
            url_data = self.url_list[index.row()]
            url_data.__setattr__(url_data_attr, value)
            self.dataChanged.emit(index, index)
            return True
        return False

    def insertRow(self, row: int, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> bool:
        self.beginInsertRows(parent, row, row)
        self.url_list.insert(row, UrlData('无', '', ''))
        self.endInsertRows()
        return True

    def removeRow(self, row: int, parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex()) -> bool:
        if row < 0 or row >= self.rowCount():
            return False
        self.beginRemoveRows(parent, row, row)
        del self.url_list[row]
        self.endRemoveRows()
        return True

    def mimeTypes(self) -> list[str]:
        return [self.URL_DATA_LIST_TYPE]

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        data = QMimeData()
        if not indexes:
            return data
        first = indexes[0]
        data.setData(self.URL_DATA_LIST_TYPE, pickle.dumps((first.row(), first.column())))
        return data

    def dropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int,
                     parent: Union[QModelIndex, QPersistentModelIndex]) -> bool:
        raw = data.data(self.URL_DATA_LIST_TYPE)
        if not row:
            return False
        source_index = self.createIndex(*pickle.loads(raw))
        changed = False
        for role in range(UrlTableItemModel.LINK_ITEM_ROLE + 1):
            source_value = self.data(source_index, role)
            if source_value:
                self.setData(parent, source_value, role)
                self.dataChanged.emit(parent, parent, [role])
                changed = True
        return changed


class UrlColumnItemDelegate(QAbstractItemDelegate):
    def __init__(self, parent: UrlTableView):
        super().__init__(parent)

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem,
                     index: Union[QModelIndex, QPersistentModelIndex]) -> QWidget:
        widget = UrlEditWidget(parent)
        widget.accepted.connect(lambda: self.commitData.emit(widget))
        widget.finished.connect(lambda: self.closeEditor.emit(widget))
        return widget

    def paint(self, painter: QPainter, option: QStyleOptionViewItem,
              index: Union[QModelIndex, QPersistentModelIndex]) -> None:
        document = QTextDocument(self.parent())
        url = index.data(UrlTableItemModel.LINK_ITEM_ROLE)
        name = index.data(Qt.ItemDataRole.DisplayRole)
        document.setHtml(f'<a href="{url}">{name}</a>')
        painter.save()
        painter.translate(option.rect.topLeft())
        document.drawContents(painter)
        painter.restore()

    def setEditorData(self, editor: QWidget, index: Union[QModelIndex, QPersistentModelIndex]) -> None:
        if not isinstance(editor, UrlEditWidget):
            return
        editor.set_value(index.data(Qt.ItemDataRole.DisplayRole), index.data(UrlTableItemModel.LINK_ITEM_ROLE))

    def setModelData(self, editor: QWidget, model: QAbstractItemModel,
                     index: Union[QModelIndex, QPersistentModelIndex]) -> None:
        if not isinstance(editor, UrlEditWidget) or not isinstance(model, UrlTableItemModel):
            return
        index.model().setItemData(index, {
            Qt.ItemDataRole.DisplayRole: editor.get_name_value(),
            UrlTableItemModel.LINK_ITEM_ROLE: editor.get_url_value()
        })
        self.sizeHintChanged.emit(index)

    def updateEditorGeometry(self, editor: QWidget, option: QStyleOptionViewItem,
                             index: Union[QModelIndex, QPersistentModelIndex]) -> None:
        rect: QRect = option.rect
        editor.move(rect.topLeft())

    def sizeHint(self, option: QStyleOptionViewItem, index: Union[QModelIndex, QPersistentModelIndex]) -> QSize:
        option.features |= QStyleOptionViewItem.ViewItemFeature.HasDisplay
        option.text = index.data(Qt.ItemDataRole.DisplayRole)
        return QApplication.style().sizeFromContents(QStyle.ContentsType.CT_ItemViewItem, option, QSize(), None)


class UrlEditWidget(QFrame):
    accepted = Signal()
    finished = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)

        layout = QFormLayout(self)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.setLayout(layout)
        self._name_widget = QLineEdit(self)
        self._name_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout.addRow('名称', self._name_widget)
        self._url_widget = QLineEdit(self)
        layout.addRow('链接', self._url_widget)

        self.setWindowFlag(Qt.WindowType.SubWindow | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet('background-color: white')
        self.setFixedWidth(300)
        self.setTabOrder(self._name_widget, self._url_widget)
        self.setFocusProxy(self._name_widget)
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, self.accept)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.reject)

    def accept(self):
        self.accepted.emit()
        self.finished.emit()

    def reject(self):
        self.finished.emit()

    def get_name_value(self):
        return self._name_widget.text()

    def get_url_value(self):
        return self._url_widget.text()

    def set_value(self, name: str, url: str):
        self._name_widget.setText(name)
        self._url_widget.setText(url)
        for w in [self._name_widget, self._url_widget]:
            if not w.hasFocus():
                w.setCursorPosition(0)


class OperatorColumnItemDelegate(QAbstractItemDelegate):
    def __init__(self, parent: QWidget):
        super().__init__(parent)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem,
              index: Union[QModelIndex, QPersistentModelIndex]) -> None:
        view: UrlTableView = option.widget
        widget = view.indexWidget(index)
        if not widget:
            widget = self.create_widget(view, index)
            view.setIndexWidget(index, widget)
        rect: QRect = option.rect
        widget.setGeometry(rect.x(), rect.y(), rect.width(), rect.height())

    @staticmethod
    def create_widget(view: UrlTableView, index: Union[QModelIndex, QPersistentModelIndex]):
        def _delete_row():
            model.removeRow(model.url_list.index(url_data))

        model: UrlTableItemModel = index.model()
        url_data = model.url_list[index.row()]
        widget = QWidget(view)
        widget.setLayout(QHBoxLayout(widget))
        widget.layout().setContentsMargins(0, 0, 0, 0)
        delete_btn = QPushButton(QPixmap(':/rowOperator/delete.svg').scaled(14, 14), None, widget)
        delete_btn.setFixedWidth(30)
        delete_btn.setStyleSheet('border: none')
        delete_btn.clicked.connect(_delete_row)
        widget.layout().addWidget(delete_btn)
        return widget

    def sizeHint(self, option: QStyleOptionViewItem, index: Union[QModelIndex, QPersistentModelIndex]) -> QSize:
        rect: QRect = option.rect
        return QSize(200, rect.height())


if __name__ == '__main__':
    def main():
        app = QApplication()
        table = UrlTableView(url_list=[UrlData('bug', '搞不定', 'https://baidu.com')])
        table.setFixedSize(1000, 600)
        table.show()

        timer = QTimer(table)
        timer.timeout.connect(lambda: print(table.get_url_datas()))
        timer.start(5_000)
        sys.exit(app.exec())


    _ = dir(url_manager_frame_rc)
    main()
