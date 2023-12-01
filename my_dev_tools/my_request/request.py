import json
from typing import Any
from urllib import parse as url_parse

from requests import Request, Response


def parse_request_body(req: Request) -> Any:
    content_type = req.headers.get('Content-Type')
    if not content_type:
        return {}
    if content_type.startswith('application/x-www-form-urlencoded'):
        params_dict = url_parse.parse_qs(req.data)
        return {k: v[0] if len(v) == 1 else v for k, v in params_dict.items()}
    elif content_type.startswith('application/json'):
        return json.loads(req.data)
    return req.data


def pase_response_body(resp: Response) -> Any:
    content_type = resp.headers.get('Content-Type')
    if not content_type:
        return {}
    elif content_type.startswith('application/json'):
        return json.loads(resp.content)
    return resp.content
