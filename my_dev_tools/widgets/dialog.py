from typing import Any, Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QAbstractButton, QInputDialog, QMessageBox, QWidget


def show_input_dialog(
        title: str,
        label: str,
        parent: Optional[QWidget] = None,
        *,
        text_value: Optional[str] = None,
        text_value_select_callback: Optional[Callable[[str], Any]] = None,
        window_modal=Qt.WindowModality.WindowModal):
    dialog = _create_input_dialog(
        title,
        parent,
        label=label,
        text_value=text_value,
        text_value_selected_func=text_value_select_callback,
        window_modal=window_modal)
    dialog.open()
    dialog.raise_()


def _create_input_dialog(
        title: str,
        parent: Optional[QWidget] = None,
        *,
        label: Optional[str] = None,
        text_value: Optional[str] = None,
        combo_box_items: Optional[list[str]] = None,
        option: Optional[QInputDialog.InputDialogOption] = None,
        text_value_selected_func: Optional[Callable[[str], None]] = None,
        window_modal=Qt.WindowModality.WindowModal):
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title)
    if label is not None:
        dialog.setLabelText(label)
    if text_value is not None:
        dialog.setTextValue(text_value)
    if combo_box_items is not None:
        dialog.setComboBoxItems(combo_box_items)
    if option is not None:
        dialog.setOption(option)
    if text_value_selected_func:
        dialog.textValueSelected.connect(text_value_selected_func)
    dialog.setWindowModality(window_modal)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    return dialog


def show_items_select_dialog(
        title: str,
        items: list[str],
        parent: Optional[QWidget] = None,
        *,
        text_value_selected_func: Optional[Callable[[str], None]] = None,
        window_modal=Qt.WindowModality.WindowModal):
    dialog = _create_input_dialog(
        title,
        parent,
        combo_box_items=items,
        option=QInputDialog.InputDialogOption.UseListViewForComboBoxItems,
        text_value_selected_func=text_value_selected_func,
        window_modal=window_modal)
    dialog.open()


def show_multi_line_input_dialog(
        title: str,
        label: str,
        parent: Optional[QWidget] = None,
        *,
        text_value: Optional[str] = None,
        text_value_select_callback: Optional[Callable[[str], None]] = None,
        window_modal=Qt.WindowModality.WindowModal):
    dialog = _create_input_dialog(
        title,
        parent,
        label=label,
        text_value=text_value,
        text_value_selected_func=text_value_select_callback,
        option=QInputDialog.InputDialogOption.UsePlainTextEditForTextInput,
        window_modal=window_modal)
    dialog.open()


def show_message(icon: QMessageBox.Icon,
                 title: str,
                 text,
                 *,
                 parent: Optional[QWidget] = None,
                 detail: Optional[str] = None,
                 standard_buttons: QMessageBox.StandardButton = QMessageBox.
                 StandardButton.Close,
                 standard_btn_func_map: dict[QMessageBox.StandardButton,
                                             Callable[[], None]] = {},
                 window_modal=Qt.WindowModality.WindowModal,
                 raise_up=True):

    def _btn_clicked(btn: QAbstractButton):
        standard_button = box.standardButton(btn)
        func = standard_btn_func_map.get(
            standard_button) if standard_btn_func_map else None
        if func:
            func()

    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setIcon(icon)
    box.setText(text)
    if standard_buttons:
        box.setStandardButtons(standard_buttons)
    if detail:
        box.setDetailedText(detail)
    box.buttonClicked.connect(_btn_clicked)
        
    box.setWindowModality(window_modal)
    box.show()
    if raise_up:
        box.raise_()
