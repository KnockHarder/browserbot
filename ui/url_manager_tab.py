import datetime
import json
import os
import sys
import time
import uuid
from typing import Optional, Union, Any

from PySide6.QtCore import Slot, Qt, QTimer, QModelIndex, QPersistentModelIndex, QAbstractItemModel, QObject, QEvent, \
    Signal
from PySide6.QtGui import QShortcut, QPalette, QBrush, QPaintEvent, QHoverEvent
from PySide6.QtWidgets import QFrame, QWidget, QFileDialog, QApplication, \
    QMenu, QAbstractItemView, QDialog, QFormLayout, QLineEdit, QVBoxLayout, QPushButton, QHBoxLayout, QTableView

import mywidgets.dialog as my_dialog
import url_manager_frame_rc
from config import get_browser
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

        my_dialog.show_input_dialog('新增标签页', '名称', self,
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

        my_dialog.show_input_dialog('重命名标签页', '名称', self,
                                    text_value=self.ui.tabWidget.tabText(index),
                                    text_value_select_callback=_rename_tab)

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
        _ = [self.setColumnWidth(idx, width) for idx, width in enumerate([100, 200, 200])]
        self.init_menu()
        self.setEditTriggers(QAbstractItemView.EditTrigger.AnyKeyPressed)
        self.doubleClicked.connect(self.go_cell_url)
        self.item_model.needInitOperatorCell.connect(self.init_operator_widget)

    def paintEvent(self, e: QPaintEvent) -> None:
        super().paintEvent(e)
        self.accessible_ui.update_add_row_buttons()

    def event(self, e: QEvent) -> bool:
        result = super().event(e)
        if isinstance(e, QHoverEvent):
            self.accessible_ui.show_add_row_button_hovered(e)
        return result

    def edit(self, index: Union[QModelIndex, QPersistentModelIndex],
             trigger: QAbstractItemView.EditTrigger = None, event=None) -> bool:
        def _update_url_column():
            url_data.name = name_input_widget.text()
            url_data.url = url_input_widget.text()
            dialog.close()
            self.model().dataChanged.emit(index, index, Qt.ItemDataRole.DisplayRole)

        if (trigger and trigger & self.editTriggers()
                and index.isValid() and index.column() == UrlTableItemModel.URL_COLUMN):
            url_data = self.row_url_data(index.row())
            dialog = QDialog(self)
            dialog.setLayout(QVBoxLayout(dialog))

            layout = QFormLayout(dialog)
            name_input_widget = QLineEdit(url_data.name, dialog)
            layout.addRow('名称', name_input_widget)
            url_input_widget = QLineEdit(url_data.url, dialog)
            layout.addRow('链接', url_input_widget)
            widget = QWidget(dialog)
            widget.setLayout(layout)
            dialog.layout().addWidget(widget)

            layout = QHBoxLayout(dialog)
            button = QPushButton('确认', dialog)
            button.clicked.connect(_update_url_column)
            layout.addWidget(button)
            button = QPushButton('取消', dialog)
            button.clicked.connect(lambda: dialog.close())
            layout.addWidget(button)
            widget = QWidget(dialog)
            widget.setLayout(layout)
            dialog.layout().addWidget(widget)
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            dialog.setWindowModality(Qt.WindowModality.WindowModal)
            dialog.show()
            return False
        return False

    def editorDestroyed(self, editor: QObject) -> None:
        self.resizeColumnToContents(0)

    def row_url_data(self, visual_row: int):
        logical_row = self.verticalHeader().logicalIndex(visual_row)
        return self.item_model.url_list[logical_row]

    def init_operator_widget(self, index: Union[QModelIndex, QPersistentModelIndex]):
        widget = TableRowOperatorWidget(self)
        widget.deleteClicked.connect(self.delete_row_by_click)
        self.setIndexWidget(index, widget)

    def delete_row_by_click(self):
        widget = self.sender()
        for row in range(self.model().rowCount()):
            index = self.model().index(row, UrlTableItemModel.OPERATOR_COLUMN)
            if widget == self.indexWidget(index):
                self.model().removeRow(row)
                return

    def go_cell_url(self, index: QModelIndex):
        if index.column() != UrlTableItemModel.URL_COLUMN:
            return
        url = self.row_url_data(index.row()).url
        if url:
            self.browser.to_url_or_open(url, activate=True)

    def rowsAboutToBeRemoved(self, parent: Union[QModelIndex, QPersistentModelIndex], start: int, end: int) -> None:
        for row in range(start, end + 1):
            for col in range(self.model().rowCount()):
                index = self.model().index(row, col, parent)
                widget = self.indexWidget(index)
                if widget:
                    widget.deleteLater()

    def get_url_datas(self) -> list:
        return [vars(self.row_url_data(i)) for i in range(self.model().rowCount())]

    def init_menu(self):
        menu = self.menu = QMenu(self)
        menu.addAction('Open Links Selected').triggered.connect(self.open_selected_urls)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda position: menu.exec(
            self.viewport().mapToGlobal(position)))

    def open_selected_urls(self):
        indexes = self.selectedIndexes()
        for idx in indexes:
            url = self.row_url_data(idx.row()).url
            if url:
                self.browser.to_url_or_open(url, activate=True)


class UrlTableItemModel(QAbstractItemModel):
    CATEGORY_COLUMN = 0
    URL_COLUMN = 1
    OPERATOR_COLUMN = 2
    URL_FOREGROUND = QBrush(QApplication.palette().color(QPalette.ColorRole.Link))
    needInitOperatorCell = Signal(QModelIndex)

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
        if not index.isValid():
            return None
        url_data = self.url_list[index.row()]
        column = index.column()
        if column == self.CATEGORY_COLUMN:
            if role == Qt.ItemDataRole.DisplayRole:
                return url_data.category
        elif column == self.URL_COLUMN:
            if role == Qt.ItemDataRole.DisplayRole:
                return url_data.name
            elif role == Qt.ItemDataRole.ForegroundRole and url_data.url:
                return self.URL_FOREGROUND
        elif column == self.OPERATOR_COLUMN:
            if role == Qt.ItemDataRole.DisplayRole:
                if not self.view.indexWidget(index):
                    self.needInitOperatorCell.emit(index)
        return None

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


class TableRowOperatorWidget(QWidget):
    deleteClicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        from ui.url_manager_row_operator_uic import Ui_UrlManagerRowOperatorGroup
        self.ui = Ui_UrlManagerRowOperatorGroup()
        self.ui.setupUi(self)

    def emit_delete_signal(self):
        self.deleteClicked.emit()


if __name__ == '__main__':
    def main():
        app = QApplication()
        table = UrlTableView(url_list=[UrlData('bug', '搞不定', 'https://baidu.com')])
        table.setFixedSize(1000, 600)
        table.show()

        timer = QTimer(table)
        timer.timeout.connect(lambda: print(table.get_url_datas()))
        timer.start(10_000)
        sys.exit(app.exec())


    _ = dir(url_manager_frame_rc)
    main()
