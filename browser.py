import asyncio
import time
from typing import Optional
from urllib.parse import quote

import requests

from browser_page import BrowserPage

FIND_INTERVAL = .1
TIMEOUT = 5.
FIND_TIMEOUT = 5


def get_browser() -> "Browser":
    return Browser()


class TabNotFoundError(Exception):
    def __init__(self, *args):
        super().__init__(*args)


class Browser:
    def __init__(self, ip='127.0.0.1', port=9100):
        self.ip = ip
        self.port = port
        self.address = f'{ip}:{port}'
        self._page_cache = list[BrowserPage]()

    @property
    def pages(self) -> list[BrowserPage]:
        pages_data = requests.get(f'http://{self.address}/json').json()
        result = list[BrowserPage]()
        for data in filter(lambda x: x['type'] == 'page', pages_data):
            page = BrowserPage(self.address, **data)
            exists = next(iter([x for x in self._page_cache if x.id == page.id]), None)
            result.append(exists if exists else BrowserPage(self.address, **data))
        self._page_cache = result
        return result

    def find_pages_by_url_prefix(self, url_prefix) -> list[BrowserPage]:
        return [x for x in self.pages if x.url.startswith(url_prefix)]

    def find_page_by_url_prefix(self, prefix: str) -> Optional[BrowserPage]:
        return max(self.find_pages_by_url_prefix(prefix), default=None, key=lambda x: len(x.url))

    def find_page_by_domain(self, domain: str) -> Optional[BrowserPage]:
        return max(filter(lambda x: domain in x.url, self.pages),
                   default=None, key=lambda y: len(y.url))

    async def find_or_open(self, url: str, activate=False, timeout=FIND_INTERVAL) -> BrowserPage:
        page = self.find_page_by_url_prefix(url)
        if page:
            if activate:
                page.activate()
            return page
        old_pages = self.pages
        requests.put(f'http://{self.address}/json/new?{quote(url)}')
        end_time = time.perf_counter() + timeout
        while len(old_pages) == len(self.pages) and time.perf_counter() < end_time:
            await asyncio.sleep(FIND_INTERVAL)
        old_ids = {x.id for x in old_pages}
        new_tab = next(iter([x for x in self.pages if x.id not in old_ids]), None)
        if not new_tab:
            raise TabNotFoundError('new tab', f'url={url}')
        return new_tab


def main():
    pass


if __name__ == '__main__':
    main()
