import datetime
import json
import os
import re
import sys
import time
import uuid
from typing import Optional

from PySide6.QtCore import Slot, Qt, QTimer
from PySide6.QtGui import QShortcut, QAction
from PySide6.QtWidgets import QFrame, QWidget, QInputDialog, QFileDialog, QApplication, \
    QTableWidgetItem, QMenu

import url_manager_frame_rc
from config import get_browser
from config import url_table_data_dir
from mywidgets import MarkdownItemDelegate


def read_tab_data_from_file(path: str):
    with open(path, 'r') as fp:
        return json.load(fp)


def main_data_file_path():
    return os.path.join(url_table_data_dir(), 'main.json')


def month_data_file_path():
    month_file = datetime.datetime.now().strftime("%Y_%m") + '.json'
    month_file = os.path.join(url_table_data_dir(), month_file)
    return month_file


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
            self.create_tab_from_data(data['tabName'], data['urls'], data.get('id'))

    @Slot()
    def add_tab(self):
        dialog = QInputDialog(self)
        dialog.setLabelText('新的TAB页名称')

        def create_new_tab(name: str):
            index = self.create_tab_from_data(name)
            self.ui.tabWidget.setCurrentIndex(index)

        dialog.textValueSelected.connect(create_new_tab)
        dialog.open()

    def create_tab_from_data(self, tab_name: str, urls: list = None, table_id: str = None):
        tab_widget = self.ui.tabWidget
        frame = UrlTableFrame(tab_widget, table_id)
        frame.update_table(urls)
        tab_widget.addTab(frame, tab_name)
        return tab_widget.count() - 1

    @Slot()
    def add_tab_from_file(self):
        dialog = QFileDialog(self, '加载链接表', url_table_data_dir(), 'JSON Files(*.json)')
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)

        def load_tab_with_selection(path: str):
            tabs = read_tab_data_from_file(path)
            dialog1 = QInputDialog(self)
            dialog1.setComboBoxItems([data['tabName'] for data in tabs])
            dialog1.setOption(QInputDialog.InputDialogOption.UseListViewForComboBoxItems)

            def load_tab_selected(tab_name: str):
                data = next(filter(lambda x: x['tabName'] == tab_name, tabs), None)
                idx = self.create_tab_from_data(tab_name, data['urls'], data.get('id'))
                self.ui.tabWidget.setCurrentIndex(idx)

            dialog1.textValueSelected.connect(load_tab_selected)
            dialog1.open()

        dialog.fileSelected.connect(load_tab_with_selection)
        dialog.open()

    def archive_tab(self, index: int):
        tab_widget = self.ui.tabWidget

        tab_name = tab_widget.tabText(index)
        table_frame: UrlTableFrame = tab_widget.widget(index)
        month_file = month_data_file_path()
        file_tabs = read_tab_data_from_file(month_file)
        file_tabs = list(filter(lambda x: x.get('id') != table_frame.id and x['tabName'] != tab_name, file_tabs))
        file_tabs.append({
            "id": table_frame.id,
            "tabName": tab_name,
            "urls": table_frame.get_url_datas()
        })
        with open(month_file, 'w') as fp:
            json.dump(file_tabs, fp, ensure_ascii=False, indent=2)
        tab_widget.removeTab(index)

    def rename_tab(self, index: int):
        tab_widget = self.ui.tabWidget

        dialog = QInputDialog(self)
        dialog.setLabelText('新的标签名')

        def rename_tab_to(name: str):
            tab_widget.setTabText(index, name)

        dialog.textValueSelected.connect(rename_tab_to)
        dialog.show()

    def save_to_json(self):
        while self.is_saving:
            print('Waiting for saving')
            time.sleep(1)
        self.is_saving = True
        try:
            tab_widget = self.ui.tabWidget
            all_data = list()
            for idx in range(tab_widget.count()):
                table_frame: UrlTableFrame = tab_widget.widget(idx)
                all_data.append({
                    "id": table_frame.id,
                    "tabName": tab_widget.tabText(idx),
                    "urls": table_frame.get_url_datas()
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


class UrlTableFrame(QFrame):
    URL_DATA_ROLE = Qt.ItemDataRole.UserRole + 1
    menu: QMenu

    def __init__(self, parent: Optional[QWidget] = None, table_id: str = None):
        super().__init__(parent)

        from ui.url_manager_table_frame_uic import Ui_Frame as UiTableFrame
        self.ui = UiTableFrame()
        self.ui.setupUi(self)
        table_widget = self.ui.tableWidget
        table_widget.setColumnWidth(0, 100)
        table_widget.setColumnWidth(1, 200)
        table_widget.setItemDelegateForColumn(1, MarkdownItemDelegate(table_widget))
        table_widget.setColumnWidth(2, 200)
        table_widget.model().rowsInserted.connect(
            lambda _, b, e: [self.init_row(i) for i in range(b, e + 1)])
        table_widget.cellDoubleClicked.connect(self.go_cell_url)
        table_widget.cellChanged.connect(self.update_cell_data)

        self.browser = get_browser()
        if not table_id:
            table_id = str(uuid.uuid1())
        self.id = table_id
        self.init_menu()

    def init_row(self, row):
        table_widget = self.ui.tableWidget
        first_cell_item = QTableWidgetItem('无')
        table_widget.setItem(row, 0, first_cell_item)
        table_widget.setItem(row, 1, QTableWidgetItem('<p style="color: LightGray">Markdown文本</p>'))
        widget = TableRowOperatorWidget(table_widget)
        widget.ui.deleteButton.clicked.connect(lambda: self.delete_row(table_widget.row(first_cell_item)))
        table_widget.setCellWidget(row, 2, widget)
        header_item = table_widget.verticalHeaderItem(row)
        if not header_item:
            header_item = QTableWidgetItem()
            table_widget.setVerticalHeaderItem(row, header_item)
        self.set_url_data(header_item, dict())

    def go_cell_url(self, row, col):
        if col != 1:
            return
        try:
            url = self.get_row_bind_data(row)['url']
            if url:
                self.browser.to_url_or_open(url, activate=True)
        except TypeError:
            pass

    def update_cell_data(self, row: int, column: int):
        data = self.get_row_bind_data(row)
        if data is None:
            return
        text = self.ui.tableWidget.item(row, column).text()
        if column == 0:
            data['category'] = text
            self.set_row_bind_data(row, data)
        elif column == 1:
            try:
                parts = re.findall(r'\[(.*?)]\((.*?)\)', text)[0]
                if parts and len(parts) == 2:
                    name, url = parts
                else:
                    name, url = text, None
            except IndexError:
                name, url = text, None
            data['name'] = name
            data['url'] = url
            self.set_row_bind_data(row, data)

    def get_row_bind_data(self, row):
        return self.ui.tableWidget.verticalHeaderItem(row).data(self.URL_DATA_ROLE)

    def set_url_data(self, item: QTableWidgetItem, data: Optional[dict]):
        item.setData(self.URL_DATA_ROLE, data)

    def set_row_bind_data(self, row: int, data: dict):
        item = self.ui.tableWidget.verticalHeaderItem(row)
        self.set_url_data(item, data)

    def update_table(self, urls: list):
        table_widget = self.ui.tableWidget
        while table_widget.rowCount() > 0:
            self.delete_row(0)
        if not urls:
            return
        for data in urls:
            self.append_data_row(data)

    def delete_row(self, row: int):
        table_widget = self.ui.tableWidget
        for col in range(table_widget.columnCount()):
            widget = table_widget.cellWidget(row, col)
            if widget:
                widget.deleteLater()
        table_widget.removeRow(row)

    def append_data_row(self, data: dict):
        table_widget = self.ui.tableWidget
        row = table_widget.rowCount()
        table_widget.insertRow(row)
        self.fill_row_content(row, data)

    def fill_row_content(self, row: int, data: dict):
        table_widget = self.ui.tableWidget
        item = table_widget.verticalHeaderItem(row)
        if not item:
            item = QTableWidgetItem(str(row + 1))
            table_widget.setVerticalHeaderItem(row, item)
        # 屏蔽更新触发逻辑
        self.set_url_data(item, None)

        def get_category():
            category = data.get('category')
            if not category:
                category = '无'
                data['category'] = category
            return category

        def markdown_url():
            name = data.get('name')
            url = data.get('url')
            return f'[{name}]({url})' if url else name

        table_widget.item(row, 0).setText(get_category())
        table_widget.item(row, 1).setText(markdown_url())
        self.set_url_data(item, data)

    def get_url_datas(self) -> list:
        table_widget = self.ui.tableWidget

        def get_visual_row_data(idx: int):
            logical_index = table_widget.verticalHeader().logicalIndex(idx)
            return self.get_row_bind_data(logical_index)

        datas = [get_visual_row_data(i) for i in range(table_widget.rowCount())]
        return [x for x in datas if x]

    def init_menu(self):
        menu = self.menu = QMenu(self)
        action = QAction('打开选中的所有链接', self)
        action.triggered.connect(self.open_selected_urls)
        menu.addAction(action)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        table_widget = self.ui.tableWidget
        self.customContextMenuRequested.connect(lambda position: menu.exec(
            table_widget.viewport().mapToGlobal(position)))

    def open_selected_urls(self):
        indexes = self.ui.tableWidget.selectedIndexes()
        for idx in indexes:
            url = self.get_row_bind_data(idx.row())['url']
            if url:
                self.browser.to_url_or_open(url, activate=False)


class TableRowOperatorWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        from ui.url_manager_row_operator_uic import Ui_UrlManagerRowOperatorGroup
        self.ui = Ui_UrlManagerRowOperatorGroup()
        self.ui.setupUi(self)


if __name__ == '__main__':
    def main():
        app = QApplication()
        frame = UrlManagerTabFrame()
        frame.show()
        sys.exit(app.exec())


    print(dir(url_manager_frame_rc))
    main()
