import mywidgets_rc
from typing import Optional

import PySide6
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QPixmap, QHoverEvent
from PySide6.QtWidgets import QTableWidget, QWidget, QPushButton, QTableWidgetItem


class AccessibleTableWidget(QTableWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.horizontalHeader().setSectionsMovable(True)
        vertical_header = self.verticalHeader()
        vertical_header.setSectionsMovable(True)
        vertical_header.sectionMoved.connect(lambda _, b, e: self.update_row_header_nums(b, e))

        self.add_row_buttons = list[QPushButton]()
        self.resize_add_row_buttons()
        self.model().rowsInserted.connect(lambda _, __: self.resize_add_row_buttons())
        self.model().rowsInserted.connect(lambda _, begin, __: self.update_row_header_nums(begin, self.rowCount()))
        self.model().rowsRemoved.connect(lambda _, __: self.resize_add_row_buttons())
        self.model().rowsRemoved.connect(lambda _, begin, __: self.update_row_header_nums(begin, self.rowCount()))

    def update_row_header_nums(self, begin, end):
        if begin > end:
            begin, end = end, begin
        for i in range(begin, end + 1):
            idx = self.verticalHeader().logicalIndex(i)
            item = self.verticalHeaderItem(idx)
            if item:
                item.setText(str(i + 1))
            else:
                self.setVerticalHeaderItem(idx, QTableWidgetItem(str(i + 1)))

    def resize_add_row_buttons(self):
        size = self.rowCount() + 1
        [x.deleteLater() for x in self.add_row_buttons[size:]]
        self.add_row_buttons = self.add_row_buttons[: size]
        buttons = self.add_row_buttons
        for i in range(len(buttons), size):
            btn = QPushButton(QPixmap(u":/tableRow/add.svg").scaled(10, 4), None, self)
            btn.move(-10, -10)
            btn.setFixedHeight(6)
            btn.setStyleSheet('background-color: #AA87CEEB; border: none')
            btn.clicked.connect(lambda: self.insertRow(i))
            btn.hide()
            buttons.append(btn)

    def paintEvent(self, e: PySide6.QtGui.QPaintEvent) -> None:
        super().paintEvent(e)
        self.update_add_row_buttons()

    def update_add_row_buttons(self):
        buttons = self.add_row_buttons
        if not buttons:
            return

        x = self.verticalHeader().x()
        y = (self.horizontalHeader().y() + self.horizontalHeader().height()
             - self.verticalOffset())
        row_width = (self.verticalHeader().width()
                     + sum([self.columnWidth(i) for i in range(self.columnCount())]))
        for i, btn in enumerate(buttons):
            btn: QPushButton = btn
            pos = QPoint(x, y - btn.height() // 2)
            if pos != btn.pos():
                btn.move(pos)
            if btn.width() != row_width:
                btn.setFixedWidth(row_width)
            y += self.rowHeight(i) if i < self.rowCount() else 0

    def event(self, e: PySide6.QtCore.QEvent) -> bool:
        result = super().event(e)
        if isinstance(e, QHoverEvent):
            self.show_add_row_button_hovered(e)
        return result

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
    print(dir(mywidgets_rc))
