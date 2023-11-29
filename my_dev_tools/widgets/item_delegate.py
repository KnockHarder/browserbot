from typing import Optional, Union

from PySide6 import QtGui, QtWidgets, QtCore
from PySide6.QtCore import QObject
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QStyledItemDelegate


class MarkdownItemDelegate(QStyledItemDelegate):
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

    def paint(self, painter: QtGui.QPainter,
              option: QtWidgets.QStyleOptionViewItem,
              index: Union[QtCore.QModelIndex, QtCore.QPersistentModelIndex]) -> None:
        self.initStyleOption(option, index)
        document = QTextDocument(self)
        document.setMarkdown(option.text)
        painter.save()
        painter.translate(option.rect.topLeft())
        document.drawContents(painter)
        painter.restore()
