#!/usr/bin/env python3
"""Check Ax3l collection over HTTPS, creating one identifiable test visit."""

import argparse
import json
import subprocess
import sys
from uuid import uuid4


def request(method: str, path: str, local: bool, payload: dict | None = None) -> dict[str, str]:
    command = [
        'curl', '--silent', '--show-error', '--max-time', '20',
        '--dump-header', '-', '--output', '/dev/null', '--request', method,
        '--header', 'Origin: https://ax3l.osoyalce.com',
    ]
    if local:
        command += ['--resolve', 'count.osoyalce.com:443:127.0.0.1', '--noproxy', '*']
    if method == 'OPTIONS':
        command += ['--header', 'Access-Control-Request-Method: POST',
                    '--header', 'Access-Control-Request-Headers: content-type']
    if payload is not None:
        command += ['--header', 'Content-Type: application/json', '--data-binary', '@-']
    command.append('https://count.osoyalce.com' + path)
    result = subprocess.run(command, input=json.dumps(payload) if payload is not None else None,
                            capture_output=True, text=True, check=True)
    # Use the final response block, after any proxy CONNECT or interim response.
    block = result.stdout.strip().split('\n\n')[-1].splitlines()
    status = int(block[0].split()[1])
    if status != 204:
        raise ValueError(f'{method} {path}: expected HTTP 204, received {status}')
    headers = {}
    for line in block[1:]:
        name, separator, value = line.partition(':')
        if separator:
            headers[name.lower()] = value.strip()
    if path == '/count' and headers.get('access-control-allow-origin') != 'https://ax3l.osoyalce.com':
        raise ValueError(f'{method} {path}: missing or incorrect CORS origin')
    print(f'PASS: {method} {path} returned HTTP 204', flush=True)
    return headers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local', action='store_true',
                        help='Connect to Caddy on 127.0.0.1, retaining HTTPS certificate checks; bypass public DNS/router routing.')
    args = parser.parse_args()
    url = 'https://ax3l.osoyalce.com/__mycount_test__/' + uuid4().hex
    print('Testing ' + ('local Caddy HTTPS' if args.local else 'public HTTPS') + '.', flush=True)
    print('This test submits one synthetic page view: ' + url, flush=True)
    posting = False
    try:
        request('GET', '/health', args.local)
        headers = request('OPTIONS', '/count', args.local)
        methods = {value.strip() for value in headers.get('access-control-allow-methods', '').split(',')}
        allowed_headers = {value.strip().lower() for value in headers.get('access-control-allow-headers', '').split(',')}
        if 'POST' not in methods or 'content-type' not in allowed_headers:
            raise ValueError('Preflight does not permit POST with Content-Type')
        posting = True
        request('POST', '/count', args.local, {
            'schema_version': 1, 'event': 'page_view', 'site': 'ax3l', 'url': url,
            'languages': ['en'], 'user_agent': 'MyCount-Ax3l-Smoke-Test/1.0',
        })
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        detail = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) else str(error)
        print('FAIL: ' + detail, file=sys.stderr)
        if posting:
            print('POST was attempted; check the test URL in the database before retrying.', file=sys.stderr)
        return 1
    print('PASS: collector acknowledged the test visit. To verify its database row, run:')
    print("SELECT COUNT(*) FROM page_views v JOIN pages p ON p.page_id = v.page_id "
          f"WHERE p.site = 'ax3l' AND p.url = '{url}';")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
