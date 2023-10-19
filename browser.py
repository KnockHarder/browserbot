import asyncio
import time
from typing import Callable, Optional, Iterator

from DrissionPage import ChromiumPage
from DrissionPage.chromium_element import ChromiumElement
from DrissionPage.commons.keys import Keys
from requests import Session

FIND_INTERVAL = .5
TIMEOUT = 5.


def loop_event():
    loop = asyncio.get_event_loop()
    if loop:
        return loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop


async def find_elements_sync(find_func: Callable[[], list[ChromiumElement]], timeout) -> list[ChromiumElement]:
    end = time.perf_counter() + timeout
    while True:
        elements = find_func()
        if elements:
            return elements
        if time.perf_counter() >= end:
            return []
        await asyncio.sleep(FIND_INTERVAL)


def find_elements_until(find_func: Callable[[], list[ChromiumElement]], timeout) -> list[ChromiumElement]:
    return loop_event().run_until_complete(
        find_elements_sync(find_func, timeout))


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
    def __init__(self, element: ChromiumElement, loc_str):
        self.element = element
        self.loc_str = loc_str

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
        return PageElement(self.element.parent(), f'{self.loc_str}->parent')

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
        return DomSearcher([self.element], self.loc_str)(loc_str, timeout)

    def child_at(self, idx: int) -> "PageElement":
        children = self.element.children()
        loc_str = f'{self.loc_str}[{idx}]'
        if idx < 0 or idx >= len(children):
            raise ElementNotFoundError(loc_str)
        return PageElement(children[idx], loc_str)

    def to_filter(self, func: Callable[["PageElement"], bool]):
        return DomFilter(iter([self.element]), self.loc_str)(func)


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
    def __init__(self, elements: Iterator[ChromiumElement], loc_str: str):
        self.elements = elements
        self.loc_str = loc_str

    def __call__(self, func: Callable[[PageElement], bool]) -> "DomFilter":
        if not self.elements:
            return self
        return DomFilter(filter(lambda x: func(x.element), self.elements), self.loc_str)

    def next(self) -> Optional[PageElement]:
        element = next(self.elements, None)
        return PageElement(element, self.loc_str) if element else None

    def to_searcher(self) -> "DomSearcher":
        return DomSearcher(list(self.elements), self.loc_str)


class DomSearcher:
    def __init__(self, elements: list[ChromiumElement], loc_str: str):
        self.elements = elements
        self.loc_str = loc_str

    def __call__(self, loc_str: str, timeout=TIMEOUT) -> "DomSearcher":
        async def async_do() -> "DomSearcher":
            return await self._async_do(lambda e: e.eles(loc_str, timeout=0),
                                        f'{self.loc_str} -> {loc_str}', timeout)

        if not self.elements:
            return self

        return loop_event().run_until_complete(async_do())

    def __getitem__(self, idx: int) -> PageElement:
        length = len(self.elements)
        if idx < -length or idx >= length:
            raise ElementNotFoundError(self.loc_str, f'idx={idx}')
        return PageElement(self.elements[idx], f'{self.loc_str}[{idx}]')

    def __len__(self):
        return len(self.elements)

    async def _async_do(self, find_func: Callable[[ChromiumElement], list[ChromiumElement]],
                        loc_str, timeout) -> "DomSearcher":
        end = time.perf_counter() + timeout
        all_found = []
        elements = self.elements
        while True:
            if not elements:
                return DomSearcher(all_found, loc_str)
            failed = list()
            for element in elements:
                found = find_func(element)
                if found:
                    all_found += found
                else:
                    failed.append(element)
            if time.perf_counter() >= end:
                return DomSearcher(all_found, loc_str)
            elements = failed
            await asyncio.sleep(FIND_INTERVAL)

    def to_filter(self, func: Callable[[PageElement], bool]):
        return DomFilter(iter(self.elements), self.loc_str)(func)

    def next(self) -> Optional[PageElement]:
        return PageElement(self.elements[0], self.loc_str) if self.elements else None

    def search_after_siblings_nodes(self, loc_str=None, timeout=TIMEOUT) -> "DomSearcher":
        async def async_do() -> DomSearcher:
            full = f'{self.loc_str}->siblings_after'
            if loc_str:
                full += f'->{loc_str}'
            return await self._async_do(lambda e: e.nexts(loc_str, 0, True), full, timeout)

        return loop_event().run_until_complete(async_do())


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
        elements = find_elements_until(lambda: self.page.eles(loc_str, timeout=0), timeout)
        return DomSearcher(elements, loc_str)


if __name__ == '__main__':
    def main():
        page = ChromiumPage()
        page.to_tab()
        page.to_main_tab()


    main()
