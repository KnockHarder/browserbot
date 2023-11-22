import os.path

from browser import Browser

DATA_DIR = os.path.expanduser('~/.my_py_datas')


def get_browser() -> Browser:
    return Browser()


def gpt_prompt_file_dir() -> str:
    return os.path.join(DATA_DIR, 'chatgpt/templates')


def url_table_data_dir() -> str:
    return os.path.join(DATA_DIR, 'url_manager')


def _init_data_dirs():
    for path in [DATA_DIR, gpt_prompt_file_dir(), url_table_data_dir()]:
        if not os.path.exists(path):
            os.mkdir(path)


_init_data_dirs()

if __name__ == '__main__':
    print(os.listdir(url_table_data_dir()))
