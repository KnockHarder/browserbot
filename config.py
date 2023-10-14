import os.path

from DrissionPage import ChromiumPage

DATA_DIR = os.path.expanduser('~/.my_py_datas')


def get_browser() -> ChromiumPage:
    return ChromiumPage()


def gpt_prompt_file_dir() -> str:
    return os.path.join(DATA_DIR, 'chatgpt/templates')


def url_table_data_dir() -> str:
    return os.path.join(DATA_DIR, 'url_manager')


if __name__ == '__main__':
    print(os.listdir(url_table_data_dir()))