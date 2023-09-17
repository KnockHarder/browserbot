import datetime
import json
import os.path
import sys
import time
from typing import Optional

from DrissionPage import ChromiumPage
from PySide6.QtCore import Slot, Signal, QTimer
from PySide6.QtWidgets import QTabWidget, QTableWidget, QPushButton, QHBoxLayout, \
    QLineEdit, QWidget, QApplication, QVBoxLayout, QInputDialog, QLayout, QFileDialog

import chromium_utils as my_chromium_utils
import qt_utils as my_qt


def create_dir_if_not_exist(data_dir):
    if not os.path.exists(data_dir):
        os.mkdir(data_dir)


def read_json_array_from_file(path):
    if not os.path.exists(path):
        return []
    with open(path) as fp:
        all_data = json.load(fp)
    return all_data


class TabNotFoundException(Exception):
    def __init__(self):
        super().__init__()


class UrlMangerWidget(QWidget):
    data_dir: str
    tab_widget: QTabWidget

    def __init__(self, parent: Optional[QWidget], browser_agent: ChromiumPage, data_dir):
        super().__init__(parent)
        self.is_saving = False
        self.chromium_agent = browser_agent
        self.data_dir = data_dir
        create_dir_if_not_exist(self.data_dir)

        self.init_from_data_file()

        timer = QTimer(self)
        timer.timeout.connect(self.save_to_json)
        timer.start(5000)

    def data_file_path(self):
        return os.path.join(self.data_dir, 'main.json')

    def init_from_data_file(self):
        content_layout = QVBoxLayout()
        self.tab_widget = QTabWidget()
        content_layout.addWidget(self.tab_widget)

        main_layout = QVBoxLayout()
        main_layout.addLayout(self.add_tool_buttons())
        main_layout.addLayout(content_layout)
        self.setLayout(main_layout)

        for tab_data in read_json_array_from_file(self.data_file_path()):
            self.add_tab(tab_data.get('tabName'), tab_data.get('urls'))

    def add_tool_buttons(self) -> QLayout:
        layout = QHBoxLayout()
        add_tab_button = QPushButton('新增页签')
        add_tab_button.clicked.connect(self.create_new_tab)

        load_tabs_button = QPushButton('加载页签')
        load_tabs_button.clicked.connect(self.load_tabs)

        layout.addWidget(add_tab_button)
        layout.addWidget(load_tabs_button)

        return layout

    @Slot()
    def create_new_tab(self):
        tab_name, confirmed = QInputDialog.getText(self, '新增页签', '页签名称')
        if confirmed and tab_name and tab_name.strip():
            self.add_tab(tab_name, [])

    @Slot()
    def load_tabs(self):
        dialog = QFileDialog(directory=self.data_dir)
        dialog.setOption(QFileDialog.Option.ReadOnly)
        if not dialog.exec():
            return
        tabs = read_json_array_from_file(dialog.selectedFiles()[0])
        for tab in tabs:
            self.add_tab(tab['tabName'], tab['urls'])

    def add_tab(self, tab_name, url_datas: list):
        tab_widget = self.tab_widget
        tab_page = TabPage(tab_widget, url_datas)
        tab_page.archive_signal.connect(self.archive_tab)
        tab_page.rename_signal.connect(self.rename_tab)
        tab_page.table.go_url_signal.connect(self.go_url)
        tab_widget.addTab(tab_page, tab_name)

    @Slot()
    def archive_tab(self):
        tab_idx = self.index_tab(self.sender())
        tab_data = self.build_table_page_json(tab_idx)
        month_file = datetime.datetime.now().strftime("%Y_%m") + '.json'
        month_file = os.path.join(self.data_dir, month_file)
        month_data = read_json_array_from_file(month_file)
        month_data = list(filter(lambda x: x['tabName'] != tab_data['tabName'], month_data))
        month_data.append(tab_data)
        with open(month_file, 'w') as fp:
            json.dump(month_data, fp, ensure_ascii=False, indent=2)
        self.tab_widget.removeTab(tab_idx)

    def index_tab(self, widget):
        tab_widget = self.tab_widget
        for idx in range(tab_widget.count()):
            if tab_widget.widget(idx) == widget:
                return idx
        raise TabNotFoundException()

    @Slot(str)
    def rename_tab(self, name):
        tab_idx = self.index_tab(self.sender())
        self.tab_widget.setTabText(tab_idx, name)

    @Slot(str)
    def go_url(self, url: str):
        chromium_page = self.chromium_agent
        my_chromium_utils.go_url(chromium_page, url)

    @Slot()
    def save_to_json(self):
        while self.is_saving:
            print('Waiting for saving')
            time.sleep(1)
        self.is_saving = True
        try:
            self.do_save_to_json()
        finally:
            self.is_saving = False

    def tab_url_table(self, idx) -> QTableWidget:
        return self.tab_widget.widget(idx).table

    def do_save_to_json(self):
        all_data = list()
        for tab_idx in range(self.tab_widget.count()):
            tab_data = self.build_table_page_json(tab_idx)
            all_data.append(tab_data)
        with open(self.data_file_path(), 'w') as fp:
            json.dump(all_data, fp, ensure_ascii=False, indent=2)

    def build_table_page_json(self, tab_idx) -> dict:
        tab_data = dict()
        tab_data['tabName'] = self.tab_widget.tabText(tab_idx)
        table = self.tab_url_table(tab_idx)
        urls = list()
        for row in range(table.rowCount()):
            urls.append({
                'name': table.cellWidget(row, 0).text(),
                'url': table.cellWidget(row, 1).text()
            })
        tab_data['urls'] = urls
        return tab_data


class TabPage(QWidget):
    archive_signal = Signal()
    rename_signal = Signal(str)

    def __init__(self, parent: Optional[QWidget], url_datas: list[dict]):
        super().__init__(parent)
        self.table = UrlTable(self, url_datas)

        layout = QVBoxLayout()
        layout.addLayout(self.init_buttons())
        main_area = QVBoxLayout()
        main_area.addWidget(self.table)
        layout.addLayout(main_area)
        self.setLayout(layout)

    def init_buttons(self):
        layout = QHBoxLayout()
        layout.addWidget(my_qt.simple_button('重命名', self.emit_rename_signal))
        layout.addWidget(my_qt.simple_button('归档', self.emit_archive_signal))
        return layout

    @Slot()
    def emit_archive_signal(self):
        self.archive_signal.emit()

    @Slot()
    def emit_rename_signal(self):
        name, confirmed = QInputDialog.getText(self, '重命名标签页', '新名称')
        if not confirmed:
            return
        self.rename_signal.emit(name)


class UrlTable(QTableWidget):
    go_url_signal = Signal(str)

    def __init__(self, parent: Optional[QWidget], url_datas: list[dict]):
        super().__init__(parent)

        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(['名称', '链接', '操作'])
        self.setColumnWidth(0, 150)
        self.setColumnWidth(1, 230)
        self.setColumnWidth(2, 370)

        if not url_datas:
            self.insert_edit_row(0, '', '')
            return
        for data in url_datas:
            row = self.rowCount()
            self.insert_edit_row(row, data['name'], data['url'])

    def insert_edit_row(self, row, name='', url=''):
        self.insertRow(row)
        self.setRowHeight(row, 40)

        self.setCellWidget(row, 0, QLineEdit(name))
        self.setCellWidget(row, 1, QLineEdit(url))
        button_cell_widget = QWidget(self)
        goto_button = QPushButton('访问', button_cell_widget)
        goto_button.clicked.connect(self.emit_go_url_signal)

        insert_button = QPushButton('插入', button_cell_widget)
        insert_button.clicked.connect(self.insert_before_row)

        append_button = QPushButton('追加', button_cell_widget)
        append_button.clicked.connect(self.append_after_row)

        move_up_button = QPushButton('上移', button_cell_widget)
        move_up_button.clicked.connect(self.move_row_up)

        move_down_button = QPushButton('下移', button_cell_widget)
        move_down_button.clicked.connect(self.move_row_down)

        delete_button = QPushButton('删除', button_cell_widget)
        delete_button.setStyleSheet('background-color: red; color: white')
        delete_button.clicked.connect(self.remove_row)
        layout = QHBoxLayout()
        layout.addWidget(goto_button)
        layout.addWidget(insert_button)
        layout.addWidget(append_button)
        layout.addWidget(move_up_button)
        layout.addWidget(move_down_button)
        layout.addWidget(delete_button)

        button_cell_widget.setLayout(layout)
        self.setCellWidget(row, 2, button_cell_widget)

    @Slot()
    def emit_go_url_signal(self):
        row = self.find_button_row(self.sender())
        self.go_url_signal.emit(self.cellWidget(row, 1).text())

    @Slot()
    def insert_before_row(self):
        self.insert_edit_row(self.find_button_row(self.sender()))

    @Slot()
    def append_after_row(self):
        self.insert_edit_row(self.find_button_row(self.sender()) + 1)

    @Slot()
    def remove_row(self):
        self.removeRow(self.find_button_row(self.sender()))

    @Slot()
    def move_row_up(self):
        row = self.find_button_row(self.sender())
        self.move_row(row, -1)

    def find_button_row(self, button) -> int:
        for row in range(self.rowCount()):
            if self.cellWidget(row, 2) == button.parent():
                return row
        raise Exception('Can not find row for the button')

    @Slot()
    def move_row_down(self):
        row = self.find_button_row(self.sender())
        self.move_row(row, 1)

    def move_row(self, row, offset):
        target_row = row + 1 + offset if offset > 0 else row + offset
        if target_row < 0 or target_row > self.rowCount():
            return
        if target_row == row \
                or (target_row == self.rowCount() and row == self.rowCount() - 1):
            return
        self.insertRow(target_row)
        if target_row < row:
            row += 1
        self.setRowHeight(target_row, self.rowHeight(row))
        for col in range(self.columnCount()):
            widget = self.cellWidget(row, col)
            self.setCellWidget(target_row, col, widget)
        self.removeRow(row)


if __name__ == '__main__':
    def main():
        app = QApplication(sys.argv)
        widget = UrlMangerWidget(None, ChromiumPage(), os.path.expanduser('~/.my_py_datas/url_manager'))
        widget.setGeometry(100, 100, 850, 700)
        widget.move(350, 1200)
        widget.show()
        sys.exit(app.exec())


    main()
