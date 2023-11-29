import os.path
import threading

DATA_DIR = os.path.expanduser('~/.my_py_datas')
_LOCK = threading.Lock()
_NEXT_ID = 1


def gpt_prompt_file_dir() -> str:
    return os.path.join(DATA_DIR, 'chatgpt/templates')


def url_table_data_dir() -> str:
    return os.path.join(DATA_DIR, 'url_manager')


def _init_data_dirs():
    for path in [DATA_DIR, gpt_prompt_file_dir(), url_table_data_dir()]:
        if not os.path.exists(path):
            os.makedirs(path)


def next_id():
    with _LOCK:
        global _NEXT_ID
        _NEXT_ID += 1
    return _NEXT_ID


_init_data_dirs()

if __name__ == '__main__':
    pass
