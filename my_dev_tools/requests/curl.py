import argparse
import shlex
import urllib.parse as url_parse

from requests import Request, PreparedRequest


def parse_curl(command: str) -> Request:
    args = _parse_args(command)
    req = Request(method=args.method)
    _set_url_and_params(req, args.url)
    _set_headers(req, args)
    _set_url_encode_data(args, req)
    if req.data:
        req.method = 'POST'
    return req


def _set_url_and_params(req: Request, url: str):
    parsed_url = url_parse.urlparse(url)
    req.url = parsed_url.scheme + '://' + parsed_url.netloc + parsed_url.path
    param_dict = url_parse.parse_qs(parsed_url.query, keep_blank_values=True)
    req.params = {k: v[0] if len(v) == 1 else v for k, v in param_dict.items()}


class CurlParserError(Exception):
    pass


def _parse_args(command) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('command')
    parser.add_argument('url')
    parser.add_argument('--location', dest='follow_redirect', action='store_true', default=False)
    parser.add_argument('--compressed', dest='compressed', action='store_true', default=False)
    parser.add_argument('-X', '--myrequest', dest='method', default='GET')
    parser.add_argument('-H', '--header', dest='headers', action='append', default=[])
    parser.add_argument('--data-urlencode', '-d', '--data', dest='data_url_encode', action='append', default=[])
    args, argv = parser.parse_known_args(shlex.split(command.replace('\n', '')))
    if argv:
        raise CurlParserError(f'Unknown arguments: {argv}')
    return args


def _set_headers(req: Request, args: argparse.Namespace):
    headers = dict()
    for raw_header in args.headers:
        parts = raw_header.split(':')
        headers[parts[0].strip()] = ':'.join(parts[1:]).strip()
    if headers:
        req.headers = headers


def _set_url_encode_data(args, req):
    form_params = dict()
    for raw_data in args.data_url_encode:
        raw_dict = url_parse.parse_qs(raw_data, keep_blank_values=True)
        for k, v in raw_dict.items():
            values = form_params[k] if k in form_params else []
            form_params[k] = values
            if isinstance(v, list):
                values.extend(v)
            else:
                values.append(v)
    form_params = {k: v[0] if len(v) == 1 else v for k, v in form_params.items()}
    if form_params:
        req.data = url_parse.urlencode(form_params)
        req.headers['Content-Type'] = 'application/x-www-form-urlencoded'


def curl_command_from_request(req: PreparedRequest) -> str:
    headers = []
    for k, v in req.headers.items():
        v = v.replace('"', '\\"')
        headers.append(f'-H "{k}: {v}"')
    data_param = ''
    content_type = req.headers.get('Content-Type')
    if content_type in ('application/x-www-form-urlencoded', 'application/json'):
        data_param = f'-d \'{req.body}\''
    return f'curl -X {req.method} {req.url} {" ".join(headers)} {data_param}'.strip()


def main():
    pass
