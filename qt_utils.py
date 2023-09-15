from typing import Callable

from PySide6.QtWidgets import QPushButton, QMessageBox, QWidget, QInputDialog


def simple_button(name: str, slot: Callable):
    button = QPushButton(name)
    button.clicked.connect(slot)
    return button


def popup_information_box(parent: QWidget, text: str, icon=QMessageBox.Icon.Information):
    message_box = QMessageBox(parent)
    message_box.setIcon(icon)
    message_box.setText(text)
    message_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    parent_pos = parent.pos()
    message_box.move(parent_pos.x() + (parent.width() - message_box.width()) / 2,
                     parent_pos.y() + (parent.height() - message_box.height()) / 2)
    message_box.exec()


def popup_confirm_box(parent: QWidget, text: str):
    message_box = QMessageBox(parent)
    message_box.setIcon(QMessageBox.Icon.Question)
    message_box.setText(text)
    message_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    message_box.setDefaultButton(QMessageBox.StandardButton.No)
    parent_pos = parent.pos()
    message_box.move(parent_pos.x() + (parent.width() - message_box.width()) / 2,
                     parent_pos.y() + (parent.height() - message_box.height()) / 2)
    return message_box.exec()