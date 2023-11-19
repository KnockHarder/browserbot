from PySide6.QtCore import Qt, QPoint, QRect, QAbstractItemModel
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QPushButton, QAbstractItemView, QTableView

import mywidgets_rc


class AccessibleTableUi:
    add_row_buttons = list[QPushButton]()

    def __init__(self, view: QTableView, model: QAbstractItemModel):
        self.view = view
        self.model = model

    def setup_ui(self):
        self.view.setStyleSheet("QTableWidget::item:selected {background-color: #6666ffff;}")
        self.view.setAlternatingRowColors(True)
        self.setup_mouse_behaviors()
        self.setup_add_row_buttons()

    def setup_mouse_behaviors(self):
        self.view.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.view.setMouseTracking(True)
        self.view.setDragEnabled(True)
        self.view.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.view.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.view.horizontalHeader().setSectionsMovable(True)
        vertical_header = self.view.verticalHeader()
        vertical_header.setSectionsMovable(True)
        vertical_header.sectionMoved.connect(lambda _, b, e: self.update_row_header_nums(b, e))

    def setup_add_row_buttons(self):
        self.resize_add_row_buttons()
        self.model.rowsInserted.connect(lambda _, __: self.resize_add_row_buttons())
        self.model.rowsInserted.connect(lambda _, begin, __: self.update_row_header_nums(begin, self.model.rowCount()))
        self.model.rowsRemoved.connect(lambda _, __: self.resize_add_row_buttons())
        self.model.rowsRemoved.connect(lambda _, begin, __: self.update_row_header_nums(begin, self.model.rowCount()))

    def update_row_header_nums(self, begin, end):
        if begin > end:
            begin, end = end, begin
        vertical_header = self.view.verticalHeader()
        for i in range(begin, end + 1):
            idx = vertical_header.logicalIndex(i)
            self.model.setHeaderData(idx, Qt.Orientation.Vertical, i + 1, Qt.ItemDataRole.DisplayRole)

    def resize_add_row_buttons(self):
        size = self.model.rowCount() + 1
        [x.deleteLater() for x in self.add_row_buttons[size:]]
        self.add_row_buttons = self.add_row_buttons[: size]
        buttons = self.add_row_buttons
        for i in range(len(buttons), size):
            btn = self.create_add_row_button(i)
            btn.hide()
            buttons.append(btn)

    def create_add_row_button(self, row: int):
        btn = QPushButton(QPixmap(u":/tableRow/add.svg").scaled(10, 4), None, self.view)
        btn.move(-10, -10)
        btn.setFixedHeight(6)
        btn.setStyleSheet('background-color: #AA87CEEB; border: none')
        btn.clicked.connect(lambda: self.model.insertRow(row))
        return btn

    def update_add_row_buttons(self):
        buttons = self.add_row_buttons
        if not buttons:
            return

        x = self.view.verticalHeader().x()
        horizontal_header = self.view.horizontalHeader()
        y = (horizontal_header.y() + horizontal_header.height()
             - self.view.verticalOffset())
        row_width = (self.view.verticalHeader().width()
                     + sum([self.view.columnWidth(i) for i in range(self.model.columnCount())]))
        for i, btn in enumerate(buttons):
            btn: QPushButton = btn
            pos = QPoint(x, y - btn.height() // 2)
            if pos != btn.pos():
                btn.move(pos)
            if btn.width() != row_width:
                btn.setFixedWidth(row_width)
            y += self.view.rowHeight(i) if i < self.model.rowCount() else 0

    def show_add_row_button_hovered(self, e):
        for btn in self.add_row_buttons:
            rect = QRect(btn.pos(), btn.rect().size())
            if not rect.contains(e.pos()):
                btn.hide()
                continue
            if btn.isHidden():
                btn.setHidden(False)
                btn.raise_()


if __name__ == '__main__':
    _ = dir(mywidgets_rc)
