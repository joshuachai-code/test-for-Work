#!/usr/bin/env python3
"""Prepare SQL tickets and execute dashboard actions without DB passwords."""
import argparse
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request
import uuid

ENDPOINT = 'https://cosec-desk.vercel.app/api/gwork'
CONTEXT = {'project_id': 'lingering-base-89796182',
           'branch_id': 'br-super-thunder-az57jivk', 'database_name': 'neondb',
           'compute_id': 'ep-fragrant-dust-az3a8wul'}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def fetch(body=None):
    request = urllib.request.Request(ENDPOINT,
        data=None if body is None else json.dumps(body).encode(),
        headers={'Content-Type': 'application/json', 'Cache-Control': 'no-cache'})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=65) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        try:
            message = json.load(error).get('error', 'Request failed')
        except (ValueError, AttributeError):
            message = 'Request failed'
        return {'ok': False, 'http_status': error.code, 'error': message,
                'outcome': 'pending_unknown' if error.code >= 500 else 'rejected',
                'request_id': (body or {}).get('request_id')}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {'ok': False, 'outcome': 'pending_unknown',
                'error': 'Connection failed. Retry the same request_id and arguments; do not create a new request ID.',
                'request_id': (body or {}).get('request_id')}

def prepare(document):
    if not isinstance(document, dict) or set(document) - {'request_id', 'operation', 'arguments'}:
        raise ValueError('Use only request_id, operation and arguments.')
    operation, arguments = document.get('operation'), document.get('arguments')
    if not isinstance(operation, str) or not isinstance(arguments, dict):
        raise ValueError('operation must be text and arguments must be an object.')
    request_id = str(uuid.UUID(document['request_id']))
    payload = json.dumps(arguments, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    sql = ("SELECT public.cosec_gwork_request('%s'::uuid, "
           "convert_from(decode('%s','hex'),'UTF8'), "
           "convert_from(decode('%s','hex'),'UTF8')::jsonb) AS request;" %
           (request_id, operation.encode().hex(), payload.hex()))
    return {**CONTEXT, 'sql': sql}

def extract_ticket(value):
    found = []
    def walk(v):
        if isinstance(v, str):
            try:
                decoded = json.loads(v)
            except (ValueError, TypeError):
                return
            if isinstance(decoded, (dict, list)):
                walk(decoded)
        elif isinstance(v, list):
            for item in v:
                walk(item)
        elif isinstance(v, dict):
            if 'request_id' in v and 'ticket' in v:
                if v.get('endpoint', ENDPOINT) != ENDPOINT:
                    raise ValueError('Unexpected endpoint; refusing to send the ticket.')
                request_id, token = str(uuid.UUID(v['request_id'])), v['ticket']
                if not isinstance(token, str) or len(token) != 64 or any(c not in '0123456789abcdef' for c in token):
                    raise ValueError('Invalid action ticket.')
                found.append({'request_id': request_id, 'ticket': token})
            else:
                for item in v.values():
                    walk(item)
    walk(value)
    if len(found) != 1:
        raise ValueError('Expected exactly one ticket from the restricted SQL tool.')
    return found[0]

def private_write(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        os.chmod(path, 0o600)
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    menu = commands.add_parser('menu'); menu.add_argument('operation', nargs='?')
    cmd = commands.add_parser('prepare'); cmd.add_argument('--request', required=True)
    execute = commands.add_parser('execute'); execute.add_argument('--receipt')
    args = parser.parse_args()
    if args.command == 'menu':
        result = fetch()
        if args.operation and 'operations' in result:
            if args.operation not in result['operations']:
                raise ValueError('Unknown operation. Read the complete menu.')
            result = result['operations'][args.operation]
    elif args.command == 'prepare':
        path = Path(args.request)
        document = json.loads(path.read_text())
        if not isinstance(document, dict):
            raise ValueError('The request must be a JSON object.')
        if 'request_id' not in document:
            document['request_id'] = str(uuid.uuid4())
            private_write(path, document)
        result = prepare(document)
    else:
        result = fetch(extract_ticket(json.load(sys.stdin)))
        if args.receipt:
            private_write(args.receipt, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get('ok') is False else 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(json.dumps({'ok': False, 'error': str(error) if isinstance(error, ValueError) and not isinstance(error, json.JSONDecodeError) else 'Invalid input or unavailable local file.'}))
        sys.exit(1)
