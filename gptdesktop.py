import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from gpt.codegen import CodeGeneratePage
from gpt.prompt import PromptManagementPage


class MyApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('GPT助手')
        self.setGeometry(100, 100, 800, 600)

        side_bar = self.create_main_side_bar()
        self.setCentralWidget(side_bar)

    def create_main_side_bar(self):
        # 创建左侧边栏
        sidebar = QTabWidget(self)
        sidebar.addTab(CodeGeneratePage(), '代码生成')
        sidebar.addTab(PromptManagementPage(), '模板管理')
        return sidebar


def main():
    app = QApplication(sys.argv)
    window = MyApp()
    window.move(window.x(), app.primaryScreen().size().height() / 2)

    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
