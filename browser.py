import asyncio
import time
from typing import Callable, Optional, Iterator

import requests
from DrissionPage import ChromiumPage
from DrissionPage.chromium_element import ChromiumElement
from DrissionPage.commons.keys import Keys

from browser_page import BrowserPage

FIND_INTERVAL = .1
TIMEOUT = 5.


def get_browser() -> "Browser":
    return Browser()


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
    def inner_html(self):
        return self.element.inner_html

    @property
    def text(self):
        return self.element.text

    def click(self):
        self.element.click()

    @property
    def parent(self) -> "PageElement":
        element = PageElement(self.element.parent(), f'{self.loc_desc}-> parent')
        if not element:
            raise ElementNotFoundError(f'{self.loc_desc}-> parent')
        return element

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
        if idx < -len(children) or idx >= len(children):
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
                time.sleep(FIND_INTERVAL)
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
                await asyncio.sleep(FIND_INTERVAL)
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
    def __init__(self, ip='127.0.0.1', port=9100):
        self.ip = ip
        self.port = port
        self.address = f'{ip}:{port}'
        self.delegate = ChromiumPage()

    @property
    def pages(self) -> list[BrowserPage]:
        pages_data = requests.get(f'http://{self.address}/json').json()
        return [BrowserPage(self.address, **data)
                for data in filter(lambda x: x['type'] == 'page', pages_data)]

    def find_pages_by_url_prefix(self, url_prefix) -> list[BrowserPage]:
        return [x for x in self.pages if x.url.startswith(url_prefix)]

    def find_page_by_url_prefix(self, prefix: str) -> Optional[BrowserPage]:
        return max(self.find_pages_by_url_prefix(prefix), default=None, key=lambda x: len(x.url))

    def find_page_by_domain(self, domain: str) -> Optional[BrowserPage]:
        return max(filter(lambda x: domain in x.url, self.pages),
                   default=None, key=lambda y: len(y.url))

    def to_page(self, page: BrowserPage = None, activate=False):
        page: BrowserPage = next(filter(lambda x: x.id == page.id, self.pages))
        if not page:
            return False
        self.delegate.to_tab(page.id, activate)

    def to_page_or_open_url(self, url: str, *, force_new_page=False, activate=False) -> BrowserPage:
        delegate = self.delegate
        if not force_new_page:
            page = self.find_page_by_url_prefix(url)
            if page:
                delegate.to_tab(page.id, activate)
                return page
        if delegate.is_alive:
            return self.open_as_new_page(url, activate)
        pages = self.pages
        if pages:
            delegate.to_tab(pages[0].id)
        else:
            self.delegate = ChromiumPage()
        return self.open_as_new_page(url, activate)

    def find_page_and_switch(self, url_prefix: str, activate=False):
        page = self.find_page_by_url_prefix(url_prefix)
        if not page:
            raise TabNotFoundError(f'url={url_prefix}')
        self.delegate.to_tab(page.id, activate)

    def open_as_new_page(self, url: str, activate: bool = False) -> BrowserPage:
        old_ids = set(map(lambda x: x.id, self.pages))
        self.delegate.run_cdp('Target.createTarget', url=url, background=True)
        while len(self.pages) == old_ids:
            time.sleep(.005)
        new_page = next(filter(lambda x: x.id not in old_ids, self.pages), None)
        if new_page:
            self.delegate.to_tab(new_page.id, activate)
        return new_page

    def search_elements(self, loc_str: str, timeout=TIMEOUT) -> "DomSearcher":
        return DomSearcher([PageElement(x, loc_str) for x
                            in self.delegate.eles(loc_str, timeout=timeout)], loc_str)

    async def async_search_elements(self, loc_str: str, timeout=TIMEOUT) -> "DomSearcher":
        end = time.perf_counter() + timeout
        while True:
            elements = self.delegate.eles(loc_str, timeout=0)
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
