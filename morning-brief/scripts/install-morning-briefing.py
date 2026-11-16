#!/usr/bin/env python3
"""Install/update one G-Work morning briefing from a G-Work cowork session.

First use the staff's Neon tool to verify cosec_gwork_identity(). Pass that
verified identity here. No database credentials are accepted or stored.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def make_payload(staff_id, staff_name, time):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', staff_id):
        raise ValueError('Use the exact verified dashboard staff ID.')
    if not staff_name.strip() or len(staff_name) > 160 or any(ord(c) < 32 for c in staff_name):
        raise ValueError('Use a valid verified staff name.')
    prompt = (Path(__file__).resolve().parent.parent / 'references' / 'morning-briefing-prompt.md').read_text()
    prompt = prompt.replace('__STAFF_ID__', staff_id).replace('__STAFF_NAME__', json.dumps(staff_name, ensure_ascii=False))
    return {
        'name': 'Cosec morning tasks - ' + staff_id,
        'description': 'Live dashboard tasks and deadlines for ' + staff_name + '; Malaysia time; read-only briefing.',
        'schedule': {'type': 'cron', 'expression': ('0' if time == '09:00' else '30') + ' 9 * * *'},
        'prompt': prompt,
        'workingDirectory': str(Path(__file__).resolve().parent.parent),
        'executionMode': 'local',
        'notifyPlatforms': [],
        'expiresAt': None,
        'enabled': True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staff-id', required=True)
    parser.add_argument('--staff-name', required=True)
    parser.add_argument('--time', choices=['09:00', '09:30'], default='09:00')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    payload = make_payload(args.staff_id, args.staff_name, args.time)
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    base = os.environ.get('LOBSTERAI_API_BASE_URL', '').rstrip('/')
    if not base:
        raise ValueError('Run this installer inside the staff member’s G-Work cowork session. No schedule was created.')
    parsed = urllib.parse.urlsplit(base)
    if parsed.scheme != 'http' or parsed.hostname not in ['127.0.0.1', 'localhost', '::1'] or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Expected G-Work’s local session API; refusing another destination.')
    if dt.datetime.now().astimezone().utcoffset() != dt.timedelta(hours=8):
        raise ValueError('Set this G-Work device’s timezone to Asia/Kuala_Lumpur before creating the 9 a.m. schedule.')
    opener = urllib.request.build_opener(NoRedirect)

    def api(method, path, body=None):
        request = urllib.request.Request(base + '/api/scheduled-tasks' + path,
            data=None if body is None else json.dumps(body, ensure_ascii=False).encode(),
            headers={'Content-Type': 'application/json', 'Accept': 'application/json'}, method=method)
        with opener.open(request, timeout=20) as response:
            result = json.load(response)
        if not result.get('success'):
            raise ValueError('G-Work did not confirm the scheduling operation. Check Scheduled Tasks before retrying.')
        return result

    existing = [t for t in api('GET', '').get('tasks', []) if t.get('name') == payload['name']]
    if len(existing) > 1:
        raise ValueError('Multiple matching reminders exist. Resolve duplicates in G-Work before installing again.')
    if existing:
        task_id = str(existing[0]['id'])
        saved = api('PUT', '/' + urllib.parse.quote(task_id, safe=''), payload)['task']
    else:
        saved = api('POST', '', payload)['task']
        task_id = str(saved['id'])
    confirmed = [t for t in api('GET', '').get('tasks', []) if str(t.get('id')) == task_id]
    if len(confirmed) != 1 or any(confirmed[0].get(k) != payload[k] for k in ['name', 'prompt', 'enabled', 'notifyPlatforms']):
        raise ValueError('Schedule write was not verified. Check Scheduled Tasks; do not create another copy.')
    if any(confirmed[0].get('schedule', {}).get(k) != value for k, value in payload['schedule'].items()):
        raise ValueError('The saved schedule differs. Check Scheduled Tasks before retrying.')
    print(json.dumps({'saved_and_checked': True, 'task_id': task_id,
        'staff_id': args.staff_id, 'time': args.time, 'timezone': 'Asia/Kuala_Lumpur',
        'frequency': 'daily', 'note': 'Run now in G-Work once to verify the Neon tool and any required tool permissions.'}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc))
