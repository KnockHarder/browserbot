import asyncio
import enum
import json
import time
from typing import Optional, Any

import requests
import websocket
from websocket import WebSocket

import config
from browser_dom import PageNode

COMMAND_SENT_CHECK_TIMEOUT = 10
COMMAND_RESULT_CHECK_INTERVAL = .01
COMMAND_TIMEOUT = 2
CONNECTION_TIMEOUT = 5
NODE_FIND_LOOP_INTERVAL = .1


class WsRequestContext:

    def __init__(self, request_id, timeout: float, params: dict):
        self.id = request_id
        self.timeout = timeout
        self.params = params
        self.requested = False
        self._expire = time.perf_counter() + timeout
        self.exception: Optional[BaseException] = None

    @property
    def alive(self):
        return not self.exception and time.perf_counter() < self._expire


class PageFlag(enum.Flag):
    NONE = 0x0
    DOM_ENABLED = 0x1


class NodeNotFoundError(Exception):
    def __init__(self, *args):
        super().__init__(*args)


class TooMuchNodeError(Exception):
    def __init__(self, *args):
        super().__init__(*args)


class CommandException(Exception):
    def __init__(self, *args):
        super().__init__(*args)


class BrowserPage:

    def __init__(self, web_tool_addr: str, **kwargs):
        self.address = web_tool_addr
        self.id = kwargs['id']
        self.url = kwargs['url']
        self.title = kwargs['title']
        self.websocket_url = kwargs['webSocketDebuggerUrl']

        self._ws: Optional[WebSocket] = None
        self.page_flag = PageFlag.NONE

    def _ensure_ws(self):
        if not self._ws:
            self._ws: WebSocket = websocket.create_connection(self.websocket_url, CONNECTION_TIMEOUT)
            self._ws.ping()

    def _recv(self, timeout: float) -> str:
        self._ensure_ws()
        timeout = max(0., timeout)
        self._ws.settimeout(timeout=timeout)
        return self._ws.recv()

    def close(self):
        if self._ws:
            self._ws.close()
        requests.get(f'http://{self.address}/json/close/{self.id}')

    def activate(self):
        requests.get(f'http://{self.address}/json/activate/{self.id}')

    async def go_url(self, url: str, *, activate=False):
        await self.command_result('Page.navigate', COMMAND_TIMEOUT, url=url)
        if activate:
            self.activate()

    async def command_result(self, command: str, timeout: float, **params) -> dict:
        request_id = config.next_id()
        self._ensure_ws()
        request = {
            'id': request_id,
            'method': command,
            'params': params
        }
        self._ws.send(json.dumps(request))
        return await self._wait_response(request_id, timeout, params)

    async def _wait_response(self, request_id: int, timeout: float, params: dict) -> Any:
        end_time = time.perf_counter() + timeout
        while True:
            try:
                raw = self._recv(end_time - time.perf_counter())
                data = json.loads(raw)
                if isinstance(data, dict) and data.get('id') == request_id:
                    if data.get('error'):
                        raise CommandException(data.get('error'), params)
                    return data['result']
            except BlockingIOError:
                pass
            if end_time < time.perf_counter():
                raise TimeoutError(f'Timeout: {timeout}', params)

    async def _ensure_dom_enabled(self):
        if PageFlag.DOM_ENABLED & self.page_flag:
            return
        await self.command_result('DOM.enable', COMMAND_TIMEOUT)
        await self.command_result('DOM.getDocument', COMMAND_TIMEOUT)

    async def _query_by_xpath(self, xpath: str, timeout: float) -> list[PageNode]:
        await self._ensure_dom_enabled()
        result: dict = await self.command_result('DOM.performSearch', query=xpath,
                                                 includeUserAgentShadowDOM=True, timeout=timeout)
        search_id = result['searchId']
        try:
            result_count = result['resultCount']
            if not result_count:
                return []
            result = await self.command_result('DOM.getSearchResults', COMMAND_TIMEOUT,
                                               searchId=search_id, fromIndex=0, toIndex=result_count)
            node_ids = result['nodeIds']
            if not node_ids:
                return []
            data_list = list()
            for _id in node_ids:
                result = await self.command_result('DOM.describeNode', COMMAND_TIMEOUT,
                                                   nodeId=_id)
                data_list.append(result['node'])
            if len(data_list) == 1:
                return [PageNode(self, f'{xpath}', **data_list[0])]
            else:
                return [PageNode(self, f'({xpath})[{i + 1}]', **data) for i, data in enumerate(data_list)]
        finally:
            await self.command_result('DOM.discardSearchResults', COMMAND_TIMEOUT,
                                      searchId=search_id)

    async def query_nodes_by_xpath(self, xpath: str, timeout: float) -> list[PageNode]:
        end_time = time.perf_counter() + timeout
        while True:
            try:
                nodes = await self._query_by_xpath(xpath, end_time - time.perf_counter())
            except TimeoutError:
                return []
            if nodes or time.perf_counter() > end_time:
                return nodes
            await asyncio.sleep(NODE_FIND_LOOP_INTERVAL)

    async def query_single_node_by_xpath(self, xpath: str, timeout: float) -> Optional[PageNode]:
        nodes = await self.query_nodes_by_xpath(xpath, timeout)
        if len(nodes) > 1:
            raise TooMuchNodeError(f'xpath: {xpath}, len: {len(nodes)}')
        return nodes[0] if nodes else None

    async def require_nodes_by_xpath(self, xpath: str, timeout: float) -> list[PageNode]:
        nodes = await self.query_nodes_by_xpath(xpath, timeout)
        if not nodes:
            raise NodeNotFoundError(f'xpath={xpath}, timeout={timeout}')
        return nodes

    async def require_single_node_by_xpath(self, xpath: str, timeout: float) -> PageNode:
        node = await self.query_single_node_by_xpath(xpath, timeout)
        if not node:
            raise NodeNotFoundError(f'xpath={xpath}, timeout={timeout}')
        return node

    async def run_js(self, expression: str, timeout: float):
        return await self.command_result('Runtime.evaluate', timeout,
                                         expression=expression)

    def __del__(self):
        if self._ws:
            self._ws.close()


def main():
    pass


if __name__ == '__main__':
    main()
