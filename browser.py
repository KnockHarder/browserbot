import asyncio
import time
from typing import Callable, Optional, Iterator

from DrissionPage import ChromiumPage
from DrissionPage.chromium_element import ChromiumElement
from DrissionPage.commons.keys import Keys
from requests import Session

FIND_INTERVAL = .5
TIMEOUT = 5.


class TabInfo:
    def __init__(self, tab_id: str, url: str, title: str):
        self.id = tab_id
        self.url = url
        self.title = title


class TabNotFoundError(Exception):
    def __init__(self, *args):
        super().__init__(args)


class ElementNotFoundError(Exception):
    def __init__(self, *args):
        super().__init__(args)


class PageElement:
    def __init__(self, element: ChromiumElement, loc_desc):
        self.element = element
        self.loc_desc = loc_desc

    @property
    def pseudo_before(self):
        return self.element.pseudo.before

    @property
    def pseudo_after(self):
        return self.element.pseudo.after

    @property
    def html(self):
        return self.element.html

    @property
    def text(self):
        return self.element.text

    def click(self):
        self.element.click()

    @property
    def parent(self) -> "PageElement":
        return PageElement(self.element.parent(), f'{self.loc_desc}-> parent')

    @property
    def attributes(self):
        return PageElementAttributes(self.element)

    def submit_input(self, text: str, append=False):
        input_ele = self.element
        if not append:
            input_ele.clear(True)
        input_ele.input(text)
        input_ele.input(Keys.ENTER)

    def search_elements(self, loc_str: str, timeout=TIMEOUT) -> "DomSearcher":
        return DomSearcher([self], self.loc_desc)(loc_str, timeout)

    async def async_search_elements(self, loc_str: str, timeout=TIMEOUT) -> "DomSearcher":
        return await DomSearcher([self], self.loc_desc).async_search(loc_str, timeout)

    def child_at(self, idx: int) -> "PageElement":
        children = self.element.children()
        loc_desc = f'{self.loc_desc}-> childAt[{idx}]'
        if idx < 0 or idx >= len(children):
            raise ElementNotFoundError(loc_desc)
        return PageElement(children[idx], loc_desc)

    def to_filter(self, func: Callable[["PageElement"], bool]):
        return DomFilter(iter([self]))(func)


class PageElementAttributes(object):
    def __init__(self, element: ChromiumElement):
        self.element = element

    def __setitem__(self, key, value):
        self.element.set.attr(key, value)

    def __getitem__(self, key):
        return self.element.attr(key)

    def __delitem__(self, key):
        self.element.set.attr(key, '')

    def __contains__(self, key):
        return True and self.element.attr(key)

    def __len__(self):
        return len(self.element.attrs)

    def __iter__(self):
        return iter(self.element.attrs)

    def __repr__(self):
        return repr(self.element.attrs)


class DomFilter:
    def __init__(self, elements: Iterator[PageElement]):
        self.elements = elements

    def __call__(self, func: Callable[[PageElement], bool]) -> "DomFilter":
        def do_filter(element: PageElement) -> bool:
            usable = func(element)
            if usable:
                func_name = func.__name__
                if '<lambda>' == func_name:
                    func_name += f'{func.__module__}{func.__code__.co_lines()}'
                element.loc_desc = f'{element.loc_desc}-> {func_name}'
            return usable

        if not self.elements:
            return self
        return DomFilter(filter(do_filter, self.elements))

    def first(self) -> Optional[PageElement]:
        return next(self.elements, None)

    def to_searcher(self) -> "DomSearcher":
        return DomSearcher(list(self.elements), 'filter')


class DomSearcher:
    def __init__(self, elements: list[PageElement], source_loc: str):
        self.loc_desc = source_loc
        self.elements = elements

    def __call__(self, loc_str: str, timeout=TIMEOUT) -> "DomSearcher":
        if not self.elements:
            return self
        return self._search_all(lambda e: e.eles(loc_str, timeout=0),
                                loc_str, timeout)

    def _search_all(self, find_no_wait: Callable[[ChromiumElement], list[ChromiumElement]],
                    loc_desc: str, timeout: float) -> "DomSearcher":
        end = time.perf_counter() + timeout
        all_found: list[PageElement] = []
        elements = self.elements
        while True:
            found, elements = _search_all_no_wait(elements, find_no_wait, loc_desc)
            all_found += found
            if elements and time.perf_counter() < end:
                time.sleep(1)
            else:
                return DomSearcher(all_found, f'{self.loc_desc}-> {loc_desc}')

    async def async_search(self, loc_str, timeout) -> "DomSearcher":
        end = time.perf_counter() + timeout
        all_found: list[PageElement] = []
        elements = self.elements
        while True:
            found, elements = _search_all_no_wait(elements, lambda e: e.eles(loc_str, timeout=0), loc_str)
            all_found += found
            if elements and time.perf_counter() < end:
                await asyncio.sleep(1)
            else:
                return DomSearcher(all_found, f'{self.loc_desc}-> {loc_str}')

    def __getitem__(self, idx: int) -> PageElement:
        length = len(self.elements)
        if idx < -length or idx >= length:
            raise ElementNotFoundError(f'{self.loc_desc}[{idx}]')
        return self.elements[idx]

    def __len__(self):
        return len(self.elements)

    def __iter__(self):
        return iter(self.elements)

    def to_filter(self, func: Callable[[PageElement], bool]):
        return DomFilter(iter(self.elements))(func)

    def first(self) -> Optional[PageElement]:
        return self.elements[0] if self.elements else None

    def search_after_siblings_nodes(self, loc_str=None, timeout=TIMEOUT) -> "DomSearcher":
        def do_find(element: ChromiumElement) -> list[ChromiumElement]:
            return element.nexts(loc_str, 0)

        loc_desc = f'-> siblings_after'
        if loc_str:
            loc_desc += f'-> {loc_str}'
        return self._search_all(do_find, loc_desc, timeout)


def _search_all_no_wait(elements: list[PageElement],
                        find_func: Callable[[ChromiumElement], list[ChromiumElement]],
                        loc_desc: str) -> tuple[list[PageElement], list[PageElement]]:
    if not elements:
        return [], []
    all_found: list[PageElement] = []
    failed: list[PageElement] = []
    for element in elements:
        found: list[ChromiumElement] = find_func(element.element)
        if found:
            all_found += [PageElement(x, f'{element.loc_desc}-> {loc_desc}') for x in found]
        else:
            failed.append(element)
    return all_found, failed


class Browser:
    def __init__(self):
        self.page = ChromiumPage()
        self.session = Session()

    def __chrome_targets(self):
        agent = self.page
        return self.session.get(f'http://{agent.address}/json').json()

    @property
    def tabs(self) -> list[TabInfo]:
        return [TabInfo(tab['id'], tab['url'], tab['title'])
                for tab in filter(lambda x: x['type'] == 'page', self.__chrome_targets())]

    def switch_to_tab(self, tab_id):
        self.page.to_tab(tab_id)

    def all_tab_with_prefix(self, url_prefix) -> list[TabInfo]:
        return [x for x in self.tabs if x.url.startswith(url_prefix)]

    def to_tab(self, tab: TabInfo = None, tab_id: str = None):
        if tab:
            tab_id = tab.id
        self.page.to_tab(tab_id)

    def is_tab_alive(self, tab: TabInfo):
        return tab in [x.id for x in self.tabs]

    def to_url_or_open(self, url: str, new_tab=False, activate=False):
        page = self.page
        if not new_tab:
            tab = self.find_tab_by_url_prefix(url)
            if tab:
                page.to_tab(tab.id, activate)
                return
        if page.is_alive:
            page.new_tab(url, activate)
            return
        tabs = self.tabs
        if tabs:
            page.to_tab(tabs[0].id)
        else:
            self.page = page = ChromiumPage()
        page.new_tab(url, activate)

    def find_tab_by_url_prefix(self, prefix: str) -> Optional[TabInfo]:
        return max(filter(lambda x: x.url.startswith(prefix), self.tabs),
                   default=None, key=lambda y: len(y.url))

    def find_and_switch(self, url_prefix: str, activate=False):
        tab = self.find_tab_by_url_prefix(url_prefix)
        if not tab:
            raise TabNotFoundError(f'url={url_prefix}')
        self.page.to_tab(tab.id, activate)

    def jump_to(self, url):
        self.page.get(url)

    def search_elements(self, loc_str: str, timeout=TIMEOUT) -> "DomSearcher":
        return DomSearcher([PageElement(x, loc_str) for x
                            in self.page.eles(loc_str, timeout=timeout)], '$')

    async def async_search_elements(self, loc_str: str, timeout=TIMEOUT) -> "DomSearcher":
        end = time.perf_counter() + timeout
        while True:
            elements = self.page.eles(loc_str, timeout=0)
            if elements or time.perf_counter() >= end:
                break
            else:
                await asyncio.sleep(FIND_INTERVAL)
        return DomSearcher([PageElement(x, loc_str) for x in elements], '$')


if __name__ == '__main__':
    def main():
        page = ChromiumPage()
        page.to_tab()
        page.to_main_tab()


    main()
