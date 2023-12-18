import enum
from typing import Any, Optional, Self, TYPE_CHECKING

from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from .browser_page import BrowserPage

COMMAND_TIMEOUT = 1


class NodePseudoType(enum.Enum):
    BEFORE = 'before'
    AFTER = 'after'

    @staticmethod
    def by_str(value: str) -> Optional["NodePseudoType"]:
        return next(filter(lambda x: x.value == value, NodePseudoType), None)


class JsExecuteException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class PageNode:
    _node_id: int = 0
    name: str
    child_count: int
    _attributes: dict
    _pseudo_type: str
    _outer_html: Optional[str] = None
    _object: Optional[dict] = None
    _parent_node: Optional[Self] = None

    def __init__(self, page: "BrowserPage", x_path: str, **kwargs):
        self.page = page
        self.x_path = x_path
        self.backend_id: int = kwargs['backendNodeId']
        self._update_node_info(kwargs)

    def _update_node_info(self, node_result: dict):
        self.name = node_result['localName']
        self.child_count = node_result['childNodeCount']
        flatter_attrs: list[str] = node_result['attributes']
        self._attributes = {flatter_attrs[i]: flatter_attrs[i + 1] for i in range(0, len(flatter_attrs), 2)}
        self._pseudo_type = node_result.get('pseudoType')
        nodes_data = node_result.get('pseudoElements')
        self.pseudo_nodes = [PageNode(self.page, '', **data) for data in (nodes_data if nodes_data else [])]

    async def update_node(self):
        node_info = await self._describe_node(backend_id=self.backend_id)
        self._update_node_info(node_info)

    async def _describe_node(self, *, node_id: int = 0, backend_id: int = 0):
        params = dict()
        if node_id:
            params['nodeId'] = node_id
        if backend_id:
            params['backendNodeId'] = backend_id
        result = await self.page.command_result('DOM.describeNode', COMMAND_TIMEOUT, **params)
        return result['node']

    def prop_value(self, name: str) -> Any:
        return self._attributes.get(name)

    def has_prop(self, name):
        return name in self._attributes

    async def set_props(self, kv_dict: Optional[dict] = None, **kwargs):
        kv_dict = dict(**kv_dict) if kv_dict else dict()
        kv_dict.update(kwargs)
        await self._ensure_node_id()
        for name, value in kv_dict.items():
            await self.page.command_result('DOM.setAttributeValue', COMMAND_TIMEOUT,
                                           nodeId=self._node_id, name=name, value=value)
        await self.update_node()

    async def _ensure_node_id(self):
        if not self._node_id:
            result = await self.page.command_result('DOM.pushNodesByBackendIdsToFrontend', COMMAND_TIMEOUT,
                                                    backendNodeIds=[self.backend_id])
            self._node_id = result['nodeIds'][0]

    @property
    def pseudo_type(self) -> Optional[NodePseudoType]:
        return NodePseudoType.by_str(self._pseudo_type)

    @property
    async def outer_html(self) -> str:
        if self._outer_html is None:
            result = await self.page.command_result('DOM.getOuterHTML', COMMAND_TIMEOUT,
                                                    backendNodeId=self.backend_id)
            self._outer_html = result['outerHTML']
        return self._outer_html

    @property
    async def text_content(self) -> str:
        return BeautifulSoup(await self.outer_html, 'html.parser').text

    @property
    async def object_id(self) -> str:
        if not self._object:
            result = await self.page.command_result('DOM.resolveNode', COMMAND_TIMEOUT,
                                                    backendNodeId=self.backend_id)
            self._object = result['object']
        return self._object['objectId']

    @property
    async def parent(self) -> Optional[Self]:
        if self.name == 'html':
            return None
        if not self._parent_node:
            nodes = await self.page.query_nodes_by_xpath(f'{self.x_path}/..', COMMAND_TIMEOUT)
            if nodes:
                self._parent_node = nodes[0]
        return self._parent_node if self._parent_node.backend_id else None

    async def js_click(self):
        result = await self._call_function_on('function() {this.click()}')
        e = result.get('exceptionDetails')
        if e:
            raise JsExecuteException(e)

    async def left_click(self):
        await self.scroll_into_view()
        result = await self.page.command_result('DOM.getContentQuads', COMMAND_TIMEOUT,
                                                backendNodeId=self.backend_id)
        x1, y1, x2, _, _, y2, _, _ = tuple(result['quads'][0])
        x, y = (x1 + x2) // 2, (y1 + y2) // 2
        for mouse_type in ['mousePressed', 'mouseReleased']:
            await self.page.command_result('Input.dispatchMouseEvent', COMMAND_TIMEOUT,
                                           type=mouse_type, x=x, y=y, button='left')

    async def _call_function_on(self, js: str):
        return await self.page.command_result('Runtime.callFunctionOn', COMMAND_TIMEOUT,
                                              functionDeclaration=js, objectId=await self.object_id)

    async def submit_input(self, content: str):
        await self.page.command_result('DOM.focus', COMMAND_TIMEOUT,
                                       backendNodeId=self.backend_id)
        await self._call_function_on('function() {this.value = ""}')
        await self.page.command_result('Input.insertText', COMMAND_TIMEOUT,
                                       text=content)
        await self.trigger_entry_key()

    async def trigger_entry_key(self):
        await self.page.command_result('Input.dispatchKeyEvent', COMMAND_TIMEOUT,
                                       type='keyDown', key='Enter', code='Enter',
                                       nativeVirtualKeyCode=13, windowsVirtualKeyCode=13)

    async def scroll_into_view(self):
        await self.page.command_result('DOM.scrollIntoViewIfNeeded', COMMAND_TIMEOUT,
                                       backendNodeId=self.backend_id)

    async def traceback_node(self) -> list[Self]:
        node = self
        path_trace = [node]
        while node:
            node = await node.parent
            if node:
                path_trace.append(node)
        return path_trace


def main():
    pass
