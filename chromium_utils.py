import time
from typing import Callable

from DrissionPage import ChromiumPage


class TabNotFoundException(Exception):
    def __int__(self, message: str):
        super().__init__(message)


def go_url(chromium_page: ChromiumPage, url: str):
    tabs = chromium_page.find_tabs(url=url)
    tab = tabs[0] if tabs and isinstance(tabs, list) else tabs
    if tab:
        chromium_page.to_tab(tab)
    else:
        chromium_page.to_main_tab()
        chromium_page.to_tab(chromium_page.new_tab(url))


def wait_elements(ele_func: Callable, timeout: int = 5):
    start = time.time()
    elements = ele_func()
    while not elements and time.time() - start < timeout:
        elements = ele_func()
    return elements


def find_all_tab_id(browser: ChromiumPage, url_prefix: str):
    return [x['id'] for x in browser.find_tabs(url=url_prefix, single=False)]