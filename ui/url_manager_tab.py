import datetime
import json
import os
import re
import sys
import time
from typing import Optional

from PySide6.QtCore import Slot, Signal, Qt, QTimer
from PySide6.QtWidgets import QFrame, QWidget, QInputDialog, QFileDialog, QApplication, \
    QTableWidgetItem

import url_manager_frame_rc
from chromium_utils import go_url
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

        self.load_main_data()
        timer = QTimer(self)
        timer.timeout.connect(self.save_to_json)
        timer.start(5000)

    def load_main_data(self):
        path = main_data_file_path()
        if not os.path.exists(path):
            return
        tabs = read_tab_data_from_file(path)
        for data in tabs:
            self.create_tab_from_data(data['tabName'], data['urls'])

    @Slot()
    def add_tab(self):
        dialog = QInputDialog(self)
        dialog.setLabelText('新的TAB页名称')
        dialog.textValueSelected.connect(self.create_tab_from_data)
        dialog.open()

    def create_tab_from_data(self, tab_name: str, urls: list = None):
        tab_widget = self.ui.tabWidget
        frame = UrlTableFrame(tab_widget)
        frame.update_table(urls)
        frame.archiveTabClicked.connect(self.archive_tab)
        frame.renameTabClicked.connect(self.rename_tab)
        tab_widget.addTab(frame, tab_name)

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
                data = next(filter(lambda data: data['tabName'] == tab_name, tabs), None)
                self.create_tab_from_data(tab_name, data['urls'])

            dialog1.textValueSelected.connect(load_tab_selected)
            dialog1.open()

        dialog.fileSelected.connect(load_tab_with_selection)
        dialog.open()

    def archive_tab(self):
        tab_widget = self.ui.tabWidget
        table_frame: UrlTableFrame = self.sender()
        tab_idx = tab_widget.indexOf(table_frame)
        tab_name = tab_widget.tabText(tab_idx)
        urls = table_frame.get_url_datas()
        month_file = month_data_file_path()
        file_tabs = read_tab_data_from_file(month_file)
        file_tabs = list(filter(lambda x: x['tabName'] != tab_name, file_tabs))
        file_tabs.append({
            "tabName": tab_name,
            "urls": urls
        })
        with open(month_file, 'w') as fp:
            json.dump(file_tabs, fp, ensure_ascii=False, indent=2)
        tab_widget.removeTab(tab_idx)

    def rename_tab(self):
        tab_widget = self.ui.tabWidget
        tab_idx = tab_widget.indexOf(self.sender())

        dialog = QInputDialog(self)
        dialog.setLabelText('新的标签名')

        def rename_tab_to(name: str):
            tab_widget.setTabText(tab_idx, name)

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
                    "tabName": tab_widget.tabText(idx),
                    "urls": table_frame.get_url_datas()
                })
            with open(main_data_file_path(), 'w') as fp:
                json.dump(all_data, fp, ensure_ascii=False, indent=2)
        finally:
            self.is_saving = False


class UrlTableFrame(QFrame):
    URL_DATA_ROLE = Qt.ItemDataRole.UserRole + 1

    archiveTabClicked = Signal()
    renameTabClicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
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
        table_widget.itemChanged.connect(self.update_edit_data)

        self.browser = get_browser()

    def init_row(self, row):
        table_widget = self.ui.tableWidget
        header_item = table_widget.verticalHeaderItem(row)
        if not header_item:
            table_widget.setVerticalHeaderItem(row, QTableWidgetItem())
        first_cell_item = QTableWidgetItem('无')
        table_widget.setItem(row, 0, first_cell_item)
        table_widget.setItem(row, 1, QTableWidgetItem('<p style="color: LightGray">Markdown文本</p>'))
        widget = TableRowOperatorWidget(table_widget)
        widget.ui.deleteButton.clicked.connect(lambda: self.delete_row(table_widget.row(first_cell_item)))
        table_widget.setCellWidget(row, 2, widget)

    def go_cell_url(self, row, col):
        if col != 1:
            return
        table_widget = self.ui.tableWidget
        try:
            url = table_widget.verticalHeaderItem(row).data(self.URL_DATA_ROLE)['url']
            if url:
                go_url(self.browser, url)
        except TypeError:
            pass

    def update_edit_data(self, item: QTableWidgetItem):
        if not item.isSelected():
            return
        table_widget = self.ui.tableWidget
        header_item = table_widget.verticalHeaderItem(table_widget.row(item))
        data = header_item.data(self.URL_DATA_ROLE)
        if not data:
            data = dict()
        column = table_widget.column(item)
        text = item.text()
        if column == 0:
            data['category'] = text
            header_item.setData(self.URL_DATA_ROLE, data)
        elif column == 1:
            parts = re.findall(r'\[(.*?)]\((.*?)\)', text)[0]
            if parts and len(parts) == 2:
                name, url = parts
            else:
                name, url = text, None
            data['name'] = name
            data['url'] = url
            header_item.setData(self.URL_DATA_ROLE, data)

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
        item.setData(self.URL_DATA_ROLE, data)

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

    @Slot()
    def archive_tab(self):
        self.archiveTabClicked.emit()

    @Slot()
    def rename_tab(self):
        self.renameTabClicked.emit()

    def get_url_datas(self) -> list:
        table_widget = self.ui.tableWidget
        datas = [table_widget.verticalHeaderItem(i).data(self.URL_DATA_ROLE)
                 for i in range(table_widget.rowCount())]
        return [x for x in datas if x]


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
