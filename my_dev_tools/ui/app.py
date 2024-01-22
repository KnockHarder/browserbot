from typing import Optional

from PySide6.QtCore import QModelIndex, Slot, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QTabWidget, QWidget, QMainWindow, QApplication, QMessageBox

from ..widgets import dialog as my_dialog


class MainTabWidget(QTabWidget):

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tabBar().hide()
        self.setStyleSheet('QTabWidget::pane {margin-top: 0px;}')

    @Slot()
    def switch_tab(self, index: QModelIndex):
        self.setCurrentIndex(index.row())


class AppWindow(QMainWindow):

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        from .app_uic import Ui_MainWindow
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        tab_widget = self.ui.main_tab_widget
        for widget in filter(
                lambda w: type(w) is QWidget and w.layout(),
                map(lambda i: tab_widget.widget(i),
                    range(tab_widget.count()))):
            widget.layout().setContentsMargins(0, 0, 0, 0)
            widget.layout().setSpacing(0)
        self._switch_tab(0)
        self.setWindowTitle("研发工具")

        self.bind_keys()

    def _switch_tab(self, index: int):
        tab_widget = self.ui.main_tab_widget
        nav_widget = self.ui.tab_name_list_widget
        if index >= tab_widget.count():
            return
        tab_widget.setCurrentIndex(index)
        nav_widget.setCurrentRow(index)

    def bind_keys(self):
        QShortcut(QKeySequence.StandardKey.Close,
                  self,
                  self._close_curr_window,
                  context=Qt.ShortcutContext.ApplicationShortcut)
        for i in range(0, 9):
            num_key = (i + 1) % 10
            QShortcut(f"Ctrl+{num_key}",
                      self,
                      lambda _i=i: self._switch_tab(_i))

    @staticmethod
    def _close_curr_window():
        window = QApplication.activeWindow()
        if not window:
            return
        my_dialog.show_message(QMessageBox.Icon.Information,
                               '确认',
                               '是否要关闭窗口?',
                               parent=window,
                               standard_buttons=QMessageBox.StandardButton.Yes
                               | QMessageBox.StandardButton.No,
                               standard_btn_func_map={
                                   QMessageBox.StandardButton.Yes: lambda: window.close()
                               })
