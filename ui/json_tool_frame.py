import json
import sys
from json import JSONDecodeError
from typing import Optional, Union, Any

import jsonpath
from PySide6.QtCore import Slot, Signal, Qt, QPoint
from PySide6.QtWidgets import QFrame, QWidget, QTreeWidgetItem, QApplication, QMessageBox, QTreeWidget, QMenu, \
    QInputDialog, QLineEdit


class JsonViewerFrame(QFrame):
    JSON_VALUE_COLUMN = 1
    JSON_PATH_ROLE = Qt.ItemDataRole.UserRole + 1
    jsonPathChanged = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        from ui.json_tool_frame_uic import Ui_json_viewer_frame
        self.ui = Ui_json_viewer_frame()
        self.ui.setupUi(self)

        self.data = {}
        self.refresh_json_tree()
        widget = self.ui.json_tree_widget
        widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        widget.customContextMenuRequested.connect(self.popup_item_menu)

    def refresh_json_tree(self):
        self.update_json_tree(self.data)

    def update_json_tree(self, data: Union[dict, list, Any], json_path='$'):
        tree_widget = self.ui.json_tree_widget
        tree_widget.clear()
        self.create_sub_items(tree_widget, data, json_path)
        if not tree_widget.topLevelItemCount():
            tree_widget.addTopLevelItem(QTreeWidgetItem(tree_widget, [str(data)]))
        self.jsonPathChanged.emit(json_path)
        self.search_json(self.ui.search_text_edit_widget.text())
        tree_widget.resizeColumnToContents(0)

    def create_sub_items(self, parent: Union[QTreeWidget, QTreeWidgetItem], data, json_path: str):
        def _add_child(_item: QTreeWidgetItem):
            if isinstance(parent, QTreeWidget):
                parent.addTopLevelItem(_item)
            else:
                parent.addChild(_item)

        if isinstance(data, dict):
            for key, value in data.items():
                item = QTreeWidgetItem(parent, [key])
                _add_child(item)
                item_path = f'{json_path}.{key}'
                item.setData(0, self.JSON_PATH_ROLE, item_path)
                self.create_sub_items(item, value, item_path)
                if not item.childCount():
                    item.setText(self.JSON_VALUE_COLUMN, str(value))
                else:
                    item.setExpanded(True)
        elif isinstance(data, list):
            for index, value in enumerate(data):
                item = QTreeWidgetItem(parent, [f'[{index}]'])
                _add_child(item)
                item_path = f'{json_path}[{index}]'
                item.setData(0, self.JSON_PATH_ROLE, item_path)
                self.create_sub_items(item, value, item_path)
                if not item.childCount():
                    item.setText(self.JSON_VALUE_COLUMN, str(value))
                else:
                    item.setExpanded(True)

    @Slot()
    def import_from_paste(self):
        text = QApplication.clipboard().text()
        try:
            self.data = json.loads(text)
        except JSONDecodeError as e:
            box = QMessageBox(QMessageBox.Icon.Critical, 'Error', e.msg,
                              QMessageBox.StandardButton.Close, self)
            box.setDetailedText(f'Line: {e.lineno}/{len(text.splitlines())}\n'
                                f'{text[max(0, e.pos - 10):min(e.pos + 10, len(text))]}')
            box.setWindowModality(Qt.WindowModality.WindowModal)
            box.show()
            return
        self.refresh_json_tree()

    @Slot(str)
    def search_json(self, key: str):
        tree_widget = self.ui.json_tree_widget
        for index in range(tree_widget.topLevelItemCount()):
            item = tree_widget.topLevelItem(index)
            item.setHidden(self.non_child_match(key, item))

    def non_child_match(self, key: str, parent: QTreeWidgetItem):
        non_child_match = True
        if parent.childCount():
            for i in range(parent.childCount()):
                child = parent.child(i)
                child.setHidden(self.non_child_match(key, child))
                non_child_match &= child.isHidden()
        if non_child_match:
            any_match = any(map(lambda x: x and key.lower() in x.lower(),
                                [parent.text(i) for i in range(parent.columnCount())]))
            return not any_match
        else:
            return False

    @Slot()
    def popup_item_menu(self, pos: QPoint):
        json_tree_widget = self.ui.json_tree_widget
        item = json_tree_widget.itemAt(pos)
        if not item:
            return

        menu = QMenu()
        action = menu.addAction('Focus')
        action.triggered.connect(lambda: self.focus_item(item))
        action = menu.addAction('Go path')
        action.triggered.connect(lambda: self.input_and_go_json_path(item))
        menu.exec(json_tree_widget.mapToGlobal(pos))

    def focus_item(self, item: QTreeWidgetItem):
        json_path = item.data(0, self.JSON_PATH_ROLE)
        if not json_path:
            return
        data = jsonpath.jsonpath(self.data, json_path)
        if not data:
            box = QMessageBox(QMessageBox.Icon.Warning, 'Error', '节点无数据',
                              QMessageBox.StandardButton.Close, self.ui.json_tree_widget)
            box.setWindowModality(Qt.WindowModality.WindowModal)
            box.show()
            return
        self.update_json_tree(data[0], json_path)

    def input_and_go_json_path(self, item: QTreeWidgetItem):
        json_path = item.data(0, self.JSON_PATH_ROLE)
        json_path = json_path if json_path else ''
        json_path, confirmed = QInputDialog.getText(
            self.ui.json_tree_widget, '输入JSON Path', 'Path', QLineEdit.EchoMode.Normal,
            json_path, Qt.WindowType.Window)
        if confirmed:
            self.go_json_path(json_path)

    def go_json_path(self, json_path: str):
        data = jsonpath.jsonpath(self.data, json_path)
        if not data:
            box = QMessageBox(QMessageBox.Icon.Critical, 'Error', 'JSON Path无有效数据',
                              QMessageBox.StandardButton.Close, self.ui.json_tree_widget)
            box.setWindowModality(Qt.WindowModality.WindowModal)
            box.show()
            return
        self.update_json_tree(data[0], json_path)


def main():
    app = QApplication()
    frame = JsonViewerFrame()
    frame.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
