import argparse
import os.path
import shlex
import urllib.request
from urllib.parse import urlencode

import requests
from requests import Request


def parse_curl(command: str) -> Request:
    args = _parse_args(command)
    req = Request(method=args.method, url=args.url)
    req.method = args.method
    _set_headers(req, args)
    _set_url_encode_data(args, req)
    return req


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
        req.data = urlencode(form_params)


def main():
    with open(os.path.expanduser('~/Downloads/curl.sh')) as f:
        command = f.read()
    req = parse_curl(command)
    with requests.session().send(req.prepare()) as resp:
        print(resp.content)


if __name__ == '__main__':
    main()
