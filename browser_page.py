import json
import time
import traceback
from threading import Thread
from typing import Callable, Optional

import requests
import websocket
from websocket import WebSocket, WebSocketTimeoutException, WebSocketConnectionClosedException

import config

SYNC_WAITING_INTERVAL = .1
RECEIVE_TIMEOUT = 1
CONNECTION_TIMEOUT = 5


class TaskForWsRecv:
    def __init__(self, task_id, timeout: float, *, callback: Callable[[dict], None] = None):
        self.id = task_id
        self._callback = callback
        self._expire = time.perf_counter() + timeout

    def do_callback(self, data: dict):
        if self._callback and time.perf_counter() <= self._expire:
            self._callback(data)


class BrowserPage:

    def __init__(self, web_tool_addr: str, **kwargs):
        self.address = web_tool_addr
        self.id = kwargs['id']
        self.url = kwargs['url']
        self.title = kwargs['title']
        self.websocket_url = kwargs['webSocketDebuggerUrl']

        self._ws: WebSocket = None
        self._ws_thread: Thread = None
        self._ws_wait_recv_task_list = list[TaskForWsRecv]()

    @property
    def _ensure_ws(self):
        if not self._ws:
            self._ws = websocket.create_connection(self.websocket_url, CONNECTION_TIMEOUT)
        if not self._ws_thread or not self._ws_thread.is_alive():
            self._ws_thread = Thread(target=self._websocket_callback, name=f'page-{self.title}-ws')
            self._ws_thread.start()
        return self._ws

    def _websocket_callback(self):
        while True:
            try:
                self._ws.settimeout(RECEIVE_TIMEOUT)
                content = self._ws.recv()
                data = json.loads(content)
            except WebSocketTimeoutException:
                continue
            except WebSocketConnectionClosedException:
                return
            except Exception as e:
                traceback.print_exception(e)
                return
            if not isinstance(data, dict):
                print('Not dict data:', data)
                return
            task = self._find_task_by_id(data)
            if task:
                self._ws_wait_recv_task_list.remove(task)
                task.do_callback(data)
            else:
                print('No id data:', data)

    def _find_task_by_id(self, task_id) -> Optional[TaskForWsRecv]:
        if not task_id:
            return None
        return next(filter(lambda t: t.id == task_id, self._ws_wait_recv_task_list), None)

    def close(self):
        if self._ws:
            self._ws.close()
        requests.get(f'http://{self.address}/json/close/{self.id}')

    def activate(self):
        requests.get(f'http://{self.address}/json/activate/{self.id}')

    def go_url(self, url: str, *, activate=False):
        self._sync_command('Page.navigate', url=url)
        if activate:
            self.activate()

    def _sync_command(self, command: str, **params):
        request_id = config.next_id()
        self._ws_wait_recv_task_list.append(TaskForWsRecv(request_id, 1, callback=lambda data: print('callback', data)))
        self._ensure_ws.send(json.dumps({
            'id': request_id,
            'method': command,
            'params': params
        }))
        while self._find_task_by_id(request_id):
            time.sleep(SYNC_WAITING_INTERVAL)

    def __eq__(self, other):
        return isinstance(other, BrowserPage) and self.id == other.id


def main():
    import json

    page_data = json.loads(requests.get('http://localhost:9100/json').text)
    page_data = [x for x in page_data if x['type'] == 'page']
    page = BrowserPage('localhost:9100', **page_data[1])
    print(page.url)
    page.go_url('http://baidu.com')


if __name__ == '__main__':
    main()
