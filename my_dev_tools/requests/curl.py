import argparse
import os.path
import shlex
import urllib.parse as url_parse

from requests import Request


def parse_curl(command: str) -> Request:
    args = _parse_args(command)
    req = Request(method=args.method)
    _set_url_and_params(req, args.url)
    _set_headers(req, args)
    _set_url_encode_data(args, req)
    return req


def _set_url_and_params(req: Request, url: str):
    parsed_url = url_parse.urlparse(url)
    req.url = parsed_url.scheme + '://' + parsed_url.netloc + parsed_url.path
    req.params = {k: v[0] if len(v) == 1 else v for k, v in url_parse.parse_qs(parsed_url.query).items()}


def _parse_args(command) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('command')
    parser.add_argument('url')
    parser.add_argument('--location', dest='follow_redirect', action='store_true', default=False)
    parser.add_argument('-X', '--myrequest', dest='method', default='GET')
    parser.add_argument('-H', '--header', dest='headers', action='append', default=[])
    parser.add_argument('--data-urlencode', dest='data_urlencode', action='append', default=[])
    args = parser.parse_args(shlex.split(command.replace('\n', '')))
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
    for raw_data in args.data_urlencode:
        parts = raw_data.split('=')
        form_params[parts[0].strip()] = '='.join(parts[1:]).strip()
    if form_params:
        req.data = url_parse.urlencode(form_params)


def main():
    with open(os.path.expanduser('~/Downloads/curl.sh')) as f:
        command = f.read()
    req = parse_curl(command)
    raw = req.data
    parsed = url_parse.parse_qs(raw)
    print(parsed)


if __name__ == '__main__':
    main()
