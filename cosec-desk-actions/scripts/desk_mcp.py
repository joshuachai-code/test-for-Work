#!/usr/bin/env python3
"""Local G-Work MCP server for the employee's existing Cosec Desk actions."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import uuid
import urllib.error
import urllib.request

import dashboard_action as dashboard


class ActionError(Exception):
    pass


def remaining(deadline):
    seconds = deadline - time.monotonic()
    if seconds <= 0:
        raise ActionError("Action time budget expired.")
    return seconds


def sql_text(value):
    return "convert_from(decode('%s','hex'),'UTF8')" % value.encode().hex()


def mint_ticket(operation, args, request_id, deadline):
    # The operator pins the connection and expected employee, outside tool arguments.
    role, employee = os.getenv("COSEC_DB_ROLE"), os.getenv("COSEC_EMPLOYEE_ID")
    if not all((role, employee, os.getenv("PGSERVICE"))):
        raise ActionError("Configure PGSERVICE, COSEC_DB_ROLE and COSEC_EMPLOYEE_ID for this employee.")
    payload = json.dumps(args, allow_nan=False, separators=(",", ":"))
    section = " AND i.tasks_enabled" if operation in TASK_WRITES or operation == "get_tasks" else ""
    sql = f"""
        SELECT public.cosec_gwork_request('{uuid.UUID(request_id)}'::uuid,
            {sql_text(operation)}, {sql_text(payload)}::jsonb)
        WHERE session_user = current_user AND current_user = {sql_text(role)}
          AND EXISTS (SELECT 1 FROM public.cosec_gwork_identity() i
                      WHERE i.database_role = current_user AND i.employee_id = {sql_text(employee)}{section});
    """
    env = {**os.environ, "PGCLIENTENCODING": "UTF8", "PGCONNECT_TIMEOUT": "5",
           "PGSSLMODE": "verify-full"}
    try:
        proc = subprocess.run(["psql", "-X", "-qAtw", "-v", "ON_ERROR_STOP=1"],
                              input=sql, capture_output=True, text=True, env=env,
                              timeout=remaining(deadline), check=False)
    except FileNotFoundError:
        raise ActionError("Install the PostgreSQL psql client and add it to G-Work's PATH.") from None
    except subprocess.TimeoutExpired:
        raise ActionError("Employee ticket request timed out.") from None
    if proc.returncode or not proc.stdout.strip():
        raise ActionError("Ticket refused. Check the restricted connection and linked employee.")
    try:
        ticket = dashboard.extract_ticket(json.loads(proc.stdout))
    except (ValueError, TypeError):
        raise ActionError("Employee connection returned an invalid action ticket.") from None
    if ticket["request_id"] != request_id:
        raise ActionError("Employee connection returned the wrong request ID.")
    return ticket


def fetch_dashboard(body=None, *, timeout):
    request = urllib.request.Request(
        dashboard.ENDPOINT,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Cache-Control": "no-cache"})
    try:
        opener = urllib.request.build_opener(dashboard.NoRedirect)
        with opener.open(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            detail = json.load(exc).get("error", "Request rejected.")
        except (ValueError, AttributeError):
            detail = "Request rejected."
        raise ActionError(f"Dashboard HTTP {exc.code}: {detail}") from None
    except (OSError, ValueError):
        raise ActionError("No usable response from the dashboard.") from None


def live_action(operation, args, request_id, deadline):
    ticket = mint_ticket(operation, args, request_id, deadline)
    result = fetch_dashboard(ticket, timeout=remaining(deadline))
    if result.get("ok") is False:
        raise ActionError(result.get("error", "Dashboard request failed."))
    return result


def unique(rows, value, field, first_name=False):
    value = value.strip().casefold()
    matches = [r for r in rows if value and str(r.get(field, "")).casefold() == value]
    if not matches and first_name and value:
        matches = [r for r in rows if str(r.get(field, "")).casefold().split()[:1] == [value]]
    if len(matches) != 1:
        raise ActionError("No unique permitted match. Provide the exact company, staff or service name.")
    return matches[0]


def resolve_task_input(op, args, read):
    out = dict(args)
    for label, key in (("company_name", "company"), ("assignee_name", "ownerId"), ("service_name", "serviceId")):
        if label in out and key in out:
            raise ActionError(f"Supply only one of {label} and {key}.")
    if "company_name" in out:
        name = out.pop("company_name")
        out["company"] = unique(read("get_directory", {"search": name})["companies"], name, "name")["c"]
    if not out.get("company"):
        raise ActionError("A company name or code is required.")
    if "assignee_name" in out or "ownerId" in out:
        identity = read("get_identity", {})
        if "assignee_name" in out:
            name = out.pop("assignee_name")
            out["ownerId"] = unique(identity["people"], name, "name", first_name=True)["id"]
        if (op == "create_task" and identity["user"]["role"] == "Team Member"
                and out["ownerId"] != identity["user"]["id"]):
            raise ActionError("A Team Member can create only their own tasks.")
    if "service_name" in out or "revision" not in out:
        workspace = read("get_workspace", {"company": out["company"]})
        out.setdefault("revision", workspace["revision"])
        if "service_name" in out:
            name = out.pop("service_name")
            name = "Certified true copies" if name.strip().casefold() == "ctc" else name
            out["serviceId"] = unique(workspace["data"].get("rates", []), name, "name")["id"]
    return out


class RequestJournal:
    """Freeze resolved identifiers/revision across restarts; store no task text or tickets."""

    def __init__(self, path):
        self.path = path

    def resolved(self, key, original, resolve):
        signature = hashlib.sha256(json.dumps(original, sort_keys=True, allow_nan=False).encode()).hexdigest()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with sqlite3.connect(self.path, timeout=1) as db:
            db.execute("CREATE TABLE IF NOT EXISTS requests (key TEXT PRIMARY KEY, fingerprint TEXT, fields TEXT)")
            row = db.execute("SELECT fingerprint, fields FROM requests WHERE key=?", (key,)).fetchone()
            if row is None:
                values = resolve()
                fixed = {k: values[k] for k in ("company", "ownerId", "serviceId", "revision") if k in values}
                db.execute("INSERT OR IGNORE INTO requests VALUES (?,?,?)", (key, signature, json.dumps(fixed)))
                row = db.execute("SELECT fingerprint, fields FROM requests WHERE key=?", (key,)).fetchone()
            if row[0] != signature:
                raise ActionError("This request ID belongs to different arguments.")
            out = {k: v for k, v in original.items() if k not in ("company_name", "assignee_name", "service_name")}
            return {**out, **json.loads(row[1])}


RESOLVE_INPUTS = {"create_task", "assign_task", "start_task", "assign_company", "set_task_guidance"}


TASK_WRITES = {"create_task", "assign_task", "start_task", "submit_task",
               "verify_task", "return_task", "set_task_guidance"}


def read_after(op, args, receipt, read):
    company = args.get("company")
    if op in TASK_WRITES:
        task_id = receipt.get("task_id") or args.get("taskId")
        if not task_id:
            return {"readback": "Task ID unavailable on replay. Look up the existing task."}
        rows = read("get_tasks", {"company": company})["tasks"]
        row = next((r for r in rows if (r.get("task_id") or r.get("id")) == task_id), None)
        if not row:
            raise ActionError("Saved task is no longer visible.")
        fields = ("task_id", "id", "title", "status", "ownerId", "company_code", "company_name",
                  "serviceName", "quantity", "dueDate", "checklist", "example", "completedDate")
        return {"task": {k: row[k] for k in fields if k in row}}
    if op in {"set_task_price", "resolve_billing", "issue_invoice"}:
        return {"billing": read("get_billing", {"company": company})}
    if op == "set_rate":
        return {"rates": read("get_workspace", {})["data"].get("rates", [])}
    if op in {"create_staff", "update_staff", "set_sections"}:
        source, field = ("get_identity", "people") if op == "create_staff" else ("get_staff", "users")
        staff_id = receipt.get("employee_id") or args.get("id")
        rows = read(source, {})[field]
        return {"staff": next((r for r in rows if r["id"] == staff_id), None)}
    if op == "set_company_access":
        return {"access": read("get_company_access", {"employee": args["employee"], "search": company})["rows"]}
    if op == "set_widgets":
        return {"widgets": read("get_identity", {})["widgets"]}
    if op.endswith("_handover") or op == "restrict_staff":
        rows = read("get_handovers", {})["packages"]
        return {"packages": [p for p in rows if (p.get("employee") or {}).get("id") == args.get("employeeId")]}
    if op in {"assign_company", "set_company_brief"}:
        progress = read("get_workspace", {"company": company})["data"]["progress"][company]
        fields = ("ownerId", "teamId", "workOwner") if op == "assign_company" else ("handover",)
        return {"company": {k: progress.get(k) for k in fields}}
    if op == "edit_records":
        data = read("get_workspace", {})["data"]
        # Return the containing collection for array edits where indexes can shift.
        records = {}
        for patch in args["patches"]:
            pointer = patch["path"].rsplit("/", 1)[0] if patch["op"] in ("add", "remove") else patch["path"]
            value = data
            for part in pointer.split("/")[1:]:
                part = part.replace("~1", "/").replace("~0", "~")
                value = value[int(part)] if isinstance(value, list) else value[part]
            records[pointer] = value
        return {"records": records}
    return {"readback": "Use the permitted read for this newly advertised operation."}


def tool_schema(name, op):
    schema = copy.deepcopy(op["inputSchema"])
    if op["write"]:
        schema["properties"]["request_id"] = {"type": "string", "format": "uuid",
            "description": "Generate one UUID per user-approved change. Reuse it and the original inputs on retry."}
        schema.setdefault("required", []).append("request_id")
    if name in RESOLVE_INPUTS:
        schema["required"] = [k for k in schema["required"] if k not in ("company", "revision")]
        schema["allOf"] = [{"oneOf": [{"required": ["company"]}, {"required": ["company_name"]}]}]
        if "ownerId" in schema["required"]:
            schema["required"].remove("ownerId")
            schema["allOf"].append({"oneOf": [{"required": ["ownerId"]}, {"required": ["assignee_name"]}]})
        for field, desc in (("company_name", "Exact permitted legal company name, in place of company."),
                            ("assignee_name", "Staff name, or a unique first name, in place of ownerId."),
                            ("service_name", "Service name or CTC, in place of serviceId.")):
            canonical = {"company_name": "company", "assignee_name": "ownerId", "service_name": "serviceId"}[field]
            if canonical in schema["properties"]:
                schema["properties"][field] = {"type": "string", "minLength": 1, "description": desc}
    if name == "get_tasks":
        schema["properties"]["mine"] = {"type": "boolean", "description": "Limit to tasks assigned to the linked employee."}
        schema["properties"]["task_id"] = {"type": "string", "description": "Limit results to this exact task ID."}
    return {"name": "cosec_" + name, "description": op["description"], "inputSchema": schema}


class Desk:
    def __init__(self, journal, fetch_catalog=fetch_dashboard, execute=live_action):
        self.journal, self.fetch_catalog, self.execute = journal, fetch_catalog, execute
        self.operations, self.expiry = {}, 0

    def menu(self, deadline):
        if time.monotonic() >= self.expiry:
            catalog = self.fetch_catalog(timeout=remaining(deadline))
            operations = catalog.get("operations")
            if not isinstance(operations, dict) or not operations:
                raise ActionError("The dashboard action catalog is unavailable.")
            self.operations, self.expiry = operations, time.monotonic() + 300
        return self.operations

    def call(self, name, arguments, deadline):
        if not name.startswith("cosec_") or not isinstance(arguments, dict):
            raise ActionError("Invalid Cosec Desk tool or arguments.")
        name = name[6:]
        operation = self.menu(deadline).get(name)
        if not operation:
            raise ActionError("Unknown Cosec Desk operation.")
        args = dict(arguments)
        allowed = tool_schema(name, operation)["inputSchema"]["properties"]
        if set(args) - set(allowed):
            raise ActionError("Unexpected tool argument. Use the advertised schema.")
        def read(op, fields):
            return self.execute(op, fields, str(uuid.uuid4()), deadline)
        if not operation["write"]:
            if name == "get_tasks":
                mine, task_id = args.pop("mine", False), args.pop("task_id", None)
                result = read(name, args)
                tasks = result["tasks"]
                if mine:
                    tasks = [t for t in tasks if t.get("ownerId") == os.environ["COSEC_EMPLOYEE_ID"]]
                if task_id:
                    tasks = [t for t in tasks if (t.get("task_id") or t.get("id")) == task_id]
                return {**result, "tasks": tasks}
            return read(name, args)
        try:
            request_id = str(uuid.UUID(args.pop("request_id")))
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ActionError("A stable UUID request_id is required for a write.") from None
        if name in RESOLVE_INPUTS:
            key = json.dumps([os.getenv("PGSERVICE"), os.getenv("COSEC_DB_ROLE"), os.getenv("COSEC_EMPLOYEE_ID"), request_id])
            args = self.journal.resolved(key, {"operation": name, **args}, lambda: resolve_task_input(name, args, read))
            args.pop("operation")
        try:
            receipt = self.execute(name, args, request_id, deadline)
        except ActionError as exc:
            raise ActionError(f"{exc} Request {request_id}. Reconcile before retrying; keep this ID for an uncertain outcome.") from None
        if receipt.get("ok") is not True or receipt.get("request_id") != request_id:
            raise ActionError("Missing commit receipt. Retry only with the original request ID and inputs.")
        try:
            evidence = read_after(name, args, receipt, read)
        except (ActionError, KeyError, IndexError, TypeError, ValueError):
            evidence = {"readback": "Committed. Current details unavailable; retry only the permitted read."}
        return {"receipt": receipt, **evidence}


VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")


def respond(msg, desk):
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}
    if "id" not in msg:
        return None
    reply = {"jsonrpc": "2.0", "id": msg["id"]}
    method, params = msg.get("method"), msg.get("params", {})
    start = time.monotonic()
    deadline = start + 22
    try:
        if method == "initialize":
            version = params.get("protocolVersion")
            result = {"protocolVersion": version if version in VERSIONS else VERSIONS[0],
                      "capabilities": {"tools": {}}, "serverInfo": {"name": "cosec-desk", "version": "1.0"}}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": [tool_schema(n, o) for n, o in desk.menu(deadline).items()]}
        elif method == "tools/call":
            out = desk.call(params["name"], params.get("arguments", {}), deadline)
            body = {"result": out, "connector_ms": round((time.monotonic() - start) * 1000)}
            result = {"content": [{"type": "text", "text": json.dumps(body, ensure_ascii=False)}]}
        else:
            return {**reply, "error": {"code": -32601, "message": "Method not found"}}
    except Exception as exc:
        # Database, JSON and OS exceptions may include SQL, tickets or credentials.
        detail = str(exc) if isinstance(exc, ActionError) else "Invalid request or unavailable connector."
        if method == "tools/call":
            result = {"isError": True, "content": [{"type": "text", "text": detail}]}
        else:
            return {**reply, "error": {"code": -32603, "message": detail}}
    return {**reply, "result": result}


def main():
    os.umask(0o077)
    state = Path(os.getenv("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    desk = Desk(RequestJournal(state / "cosec-desk" / "resolved-requests.sqlite3"))
    for line in sys.stdin:
        try:
            reply = respond(json.loads(line), desk)
        except ValueError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Invalid JSON"}}
        if reply is not None:
            print(json.dumps(reply, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
