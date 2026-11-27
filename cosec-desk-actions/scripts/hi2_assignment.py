"""Check assignment eligibility or create one task through the current employee's Hi2 connection."""
import argparse
from datetime import date
import json
import os
from pathlib import Path
import sys
from time import perf_counter_ns
import uuid

import dashboard_action as api


class AssignmentError(ValueError):
    pass


def paired_row(response, names):
    """Hi2 may wrap the one SQL row in JSON strings, lists or MCP content blocks."""
    rows = []

    def visit(value):
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
            except ValueError:
                return
            if isinstance(decoded, (list, dict)):
                visit(decoded)
        elif isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            if all(name in value for name in names):
                rows.append(value)
            else:
                for item in value.values():
                    visit(item)

    visit(response)
    if len(rows) != 1:
        raise AssignmentError("Expected a single Hi2 result for an active caller with Tasks access.")
    row = rows[0]
    if 'identity_ticket' in names and row.get('tasks_enabled') is not True:
        raise AssignmentError('Tasks access is disabled or unverified for the authenticated caller.')
    tickets = {name: api.extract_ticket(row[name]) for name in names}
    if len({t['request_id'] for t in tickets.values()}) != len(tickets):
        raise AssignmentError("Expected a distinct ticket for each operation.")
    return row, tickets


def fetch(ticket):
    result = api.fetch(ticket)
    if result.get('ok') is False:
        raise AssignmentError(result.get('error', 'Dashboard request failed.'))
    if result.get('request_id') != ticket['request_id']:
        raise AssignmentError("No matching dashboard response. Retain the original request.")
    return result


def match(rows, text, keys, label, first_name=False):
    if not isinstance(text, str) or not text.strip():
        raise AssignmentError(f"Supply the {label}.")
    needle = text.strip().casefold()
    hits = [r for r in rows if any(str(r.get(k, '')).casefold() == needle for k in keys)]
    if not hits and first_name:
        hits = [r for r in rows if str(r.get('name', '')).casefold().split()[:1] == [needle]]
    if len(hits) != 1:
        raise AssignmentError(f"No unique eligible {label}. Ask for the exact name or ID.")
    return hits[0]


def resolve_recipient(request, user, people, workspace):
    if user['role'] not in ('Team Leader', 'Director', 'Team Member'):
        raise AssignmentError("Unsupported assignment role.")
    data = workspace['data']
    company = match(data['entities'], request.get('company'), ('c', 'name', 'reg'), 'company')
    team = data['progress'][company['c']].get('teamId')
    if not team or (user['role'] != 'Director' and user.get('team_id') != team):
        raise AssignmentError("This company is outside the caller's team.")
    eligible = [p for p in people if p.get('active', True) and p.get('team_id') == team]
    owner = match(eligible, request.get('assignee'), ('id', 'name'), 'assignee', first_name=True)
    if user['role'] == 'Team Member' and user['id'] != owner['id']:
        raise AssignmentError("Team Members can create tasks only for themselves.")
    return company, owner


def resolve(request, user, people, workspace):
    if set(request) - {'company', 'assignee', 'service', 'title', 'quantity', 'due_date'}:
        raise AssignmentError("Unexpected request field. Use the standalone task assignment fields.")
    company, owner = resolve_recipient(request, user, people, workspace)
    args = {'revision': workspace['revision'], 'company': company['c'], 'ownerId': owner['id']}
    if request.get('service'):
        name = request['service']
        if isinstance(name, str) and name.strip().casefold() == 'ctc':
            name = 'Certified true copies'
        args['serviceId'] = match(workspace['data'].get('rates', []), name, ('id', 'name'), 'service')['id']
    if request.get('title'):
        args['title'] = request['title']
    if not ('title' in args or 'serviceId' in args):
        raise AssignmentError("Supply the task title or service.")
    if 'quantity' in request:
        qty = request['quantity']
        if 'serviceId' not in args or type(qty) is not int or not 1 <= qty <= 9999:
            raise AssignmentError("An explicit quantity requires a service and 1–9999 whole units.")
        args['quantity'] = qty
    if 'due_date' in request:
        due = request['due_date']
        if not isinstance(due, str) or date.fromisoformat(due).isoformat() != due:
            raise AssignmentError("Use a valid YYYY-MM-DD due date.")
        args['dueDate'] = due
    return args


def read_context(hi2_result):
    row, tickets = paired_row(hi2_result, ('identity_ticket', 'workspace_ticket'))
    started = perf_counter_ns()
    identity = fetch(tickets['identity_ticket'])
    identity_done = perf_counter_ns()
    user = identity.get('user', {})
    if not user.get('id') or user['id'] != row.get('employee_id') or user.get('role') != row.get('staff_role'):
        raise AssignmentError("The authenticated staff identity changed. Stop before creating a task.")
    sections = user.get('allowed_sections')
    if user['role'] != 'Director' and sections is not None and 'tasks' not in sections:
        raise AssignmentError('Tasks access is disabled for this employee.')
    workspace_started = perf_counter_ns()
    workspace = fetch(tickets['workspace_ticket'])
    timings = {'identity_read': (identity_done - started) // 1_000_000,
               'workspace_read': (perf_counter_ns() - workspace_started) // 1_000_000}
    return row, user, identity['people'], workspace, timings


def check(document):
    request = document['request']
    if set(request) != {'company', 'assignee'}:
        raise AssignmentError("The eligibility check takes only company and assignee.")
    _, user, people, workspace, timings = read_context(document['hi2'])
    company, owner = resolve_recipient(request, user, people, workspace)
    return {'eligible': True, 'tasks_enabled': True,
            'caller': {k: user[k] for k in ('id', 'name', 'role', 'team_id')},
            'company': {'code': company['c'], 'name': company['name']},
            'assignee': {k: owner[k] for k in ('id', 'name', 'role', 'team_id')},
            'timings_ms': timings}


def plan(document):
    row, user, people, workspace, _ = read_context(document['hi2'])
    args = resolve(document['request'], user, people, workspace)
    return {'request_id': str(uuid.uuid4()), 'operation': 'create_task', 'arguments': args,
            'employee_id': user['id'], 'staff_role': user['role'], 'database_login': row['database_login']}


def sql_text(value):
    return "convert_from(decode('%s','hex'),'UTF8')" % value.encode('utf-8').hex()


def write_call(saved):
    args = saved['arguments']
    req = api.prepare({key: saved[key] for key in ('request_id', 'operation', 'arguments')})
    create_sql = req['sql'].rstrip().rstrip(';')
    # Both tickets are issued under the caller seen at preflight. get_tasks is
    # executed only after the successful create, so it sees the committed row.
    req['sql'] = f"""SELECT ({create_sql}) AS create_ticket,
        public.cosec_gwork_request(gen_random_uuid(), 'get_tasks',
            jsonb_build_object('company', {sql_text(args['company'])})) AS verify_ticket
        WHERE (SELECT count(*) = 1 AND bool_and(i.tasks_enabled AND i.database_role = current_user
            AND i.database_role = {sql_text(saved['database_login'])}
            AND i.employee_id = {sql_text(saved['employee_id'])}
            AND i.staff_role = {sql_text(saved['staff_role'])}) FROM public.cosec_gwork_identity() i);"""
    return req


def finish(saved, response):
    _, tickets = paired_row(response, ('create_ticket', 'verify_ticket'))
    if tickets['create_ticket']['request_id'] != saved['request_id']:
        raise AssignmentError("The write ticket does not match the saved request.")
    receipt = fetch(tickets['create_ticket'])
    if not receipt.get('ok') or receipt.get('operation') != 'create_task':
        raise AssignmentError("Creation is unconfirmed. Reuse the original request ID and inputs.")
    task_id = receipt.get('task_id')
    if not task_id:
        return {'committed': True, 'request_id': saved['request_id'],
                'readback': 'Committed receipt has no task ID. Reconcile through a permitted read.'}
    result = {'committed': True, 'request_id': saved['request_id'], 'task_id': task_id}
    try:
        tasks = fetch(tickets['verify_ticket'])['tasks']
        row = next(t for t in tasks if (t.get('task_id') or t.get('id')) == task_id)
        fields = ('ownerId', 'status', 'quantity', 'dueDate', 'company_code', 'title', 'serviceId')
        result['task'] = {k: row[k] for k in fields if k in row}
        expected = {k: v for k, v in saved['arguments'].items() if k in fields}
        expected.update(status='open', company_code=saved['arguments']['company'])
        result['verified'] = all(row.get(k) == v for k, v in expected.items())
    except (AssignmentError, KeyError, StopIteration, TypeError, ValueError):
        result.update(verified=False, readback='Creation committed. Retry only the permitted read.')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    steps = parser.add_subparsers(dest='step', required=True)
    steps.add_parser('check', help='Read caller, company and recipient eligibility.')
    for step in ('plan', 'resume', 'finish'):
        command = steps.add_parser(step)
        command.add_argument('file', type=Path, help='Private plan file, unique to this instruction.')
    args = parser.parse_args()
    if args.step == 'check':
        print(json.dumps(check(json.load(sys.stdin)), ensure_ascii=False))
        return
    if args.step == 'plan':
        saved = plan(json.load(sys.stdin))
        # Exclusive creation prevents retries or concurrent runs from replacing a write ID.
        with open(args.file, 'x', opener=lambda path, flags: os.open(path, flags, 0o600)) as f:
            json.dump(saved, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
    else:
        saved = json.loads(args.file.read_text())
    result = finish(saved, json.load(sys.stdin)) if args.step == 'finish' else write_call(saved)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except FileExistsError:
        sys.exit('This plan exists. Use resume with the original file for that instruction.')
    except AssignmentError as exc:
        sys.exit(str(exc))
    except (ValueError, OSError, KeyError, TypeError, AttributeError):
        sys.exit('Invalid or incomplete assignment inputs. Preserve the plan if a write was attempted.')
