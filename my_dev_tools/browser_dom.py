import enum
from typing import Any, Optional

from bs4 import BeautifulSoup

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
    name: str
    child_count: int
    _attributes: dict
    _pseudo_type: str
    _outer_html: Optional[str]
    _object: Optional[dict]

    def __init__(self, page: "BrowserPage", x_path: str, **kwargs):
        self.page = page
        self.x_path = x_path
        self.id: int = kwargs['nodeId']
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
        self._outer_html = None
        self._object = None

    async def update_node(self):
        result = await self.describe_node()
        self._update_node_info(result['node'])

    async def describe_node(self):
        return await self.page.command_result('DOM.describeNode', COMMAND_TIMEOUT,
                                              backendNodeId=self.backend_id)

    def prop_value(self, name: str) -> Any:
        return self._attributes.get(name)

    def has_prop(self, name):
        return name in self._attributes

    async def set_props(self, kv_dict: Optional[dict] = None, **kwargs):
        kv_dict = dict(**kv_dict) if kv_dict else dict()
        kv_dict.update(kwargs)
        result = await self.page.command_result('DOM.pushNodesByBackendIdsToFrontend', COMMAND_TIMEOUT,
                                                backendNodeIds=[self.backend_id])
        node_id = result['nodeIds'][0]
        for name, value in kv_dict.items():
            await self.page.command_result('DOM.setAttributeValue', COMMAND_TIMEOUT,
                                           nodeId=node_id, name=name, value=value)
        await self.update_node()

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
        await self.page.command_result('Input.dispatchKeyEvent', COMMAND_TIMEOUT,
                                       type='keyDown', key='Enter', code='Enter',
                                       nativeVirtualKeyCode=13, windowsVirtualKeyCode=13)

    async def scroll_into_view(self):
        await self.page.command_result('DOM.scrollIntoViewIfNeeded', COMMAND_TIMEOUT,
                                       backendNodeId=self.backend_id)


if __name__ == '__main__':
    from browser_page import BrowserPage

    _ = BrowserPage
