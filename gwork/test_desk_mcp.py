import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "cosec-desk-actions" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import desk_mcp as m


def op(write=False):
    return {"write": write, "description": "test",
            "inputSchema": {"type": "object", "additionalProperties": False,
                            "properties": {k: {} for k in ("company","revision","ownerId","serviceId","quantity","dueDate","taskId","widgets")}, "required": ["company", "revision"] if write else []}}


class ConnectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "journal.sqlite3"
        self.calls = []
        self.catalog_hits = 0
        self.revision = 17
        self.task = {"task_id": "task-1", "company_code": "FASB", "status": "open",
                     "ownerId": "aisha", "quantity": 5, "dueDate": "2026-11-30"}
        self.people = [{"id": "aisha", "name": "Aisha Rahman"}]
        self.menu = {name: op(name in ("create_task", "verify_task", "set_widgets")) for name in
                     ("get_tasks", "get_directory", "get_workspace", "get_identity",
                      "create_task", "verify_task", "set_widgets", "future_read")}

        def catalog(**kwargs):
            self.catalog_hits += 1
            return {"operations": self.menu}

        self.desk = m.Desk(m.RequestJournal(self.path), catalog, self.execute)
        env = patch.dict(os.environ, {"COSEC_EMPLOYEE_ID": "daniel", "COSEC_DB_ROLE": "gwork_daniel",
                                      "PGSERVICE": "staff-service"})
        env.start()
        self.addCleanup(env.stop)
        self.args = {"company_name": "Fast AI Sdn Bhd", "assignee_name": "Aisha",
                     "service_name": "CTC", "quantity": 5, "dueDate": "2026-11-30",
                     "request_id": str(uuid.uuid4())}

    def execute(self, name, args, req, deadline):
        self.calls.append((name, args.copy(), req))
        if name == "get_directory":
            return {"companies": [{"name": "Fast AI Sdn Bhd", "c": "FASB"}]}
        if name == "get_identity":
            return {"user": {"id": "daniel", "role": "Team Leader"}, "people": self.people, "widgets": []}
        if name == "get_workspace":
            return {"revision": self.revision, "data": {"rates": [{"name": "Certified true copies", "id": "standard-2"}]}}
        if name == "get_tasks":
            return {"tasks": [self.task, {"task_id": "other", "ownerId": "daniel"}]}
        if name == "verify_task" and args.get("revision") != self.revision:
            raise m.ActionError("409: workspace changed")
        return {"ok": True, "request_id": req, "task_id": "task-1"}

    def call(self, name, args):
        return self.desk.call("cosec_" + name, args, time.monotonic() + 15)

    def test_catalog_and_input_schema_are_live_and_cached(self):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        for _ in range(2):
            tools = {t["name"]: t for t in m.respond(msg, self.desk)["result"]["tools"]}
            self.assertIn("cosec_future_read", tools)
            schema = tools["cosec_create_task"]["inputSchema"]
            self.assertIn("request_id", schema["required"])
            self.assertIn("assignee_name", schema["properties"])
            self.assertIn({"required": ["company_name"]}, schema["allOf"][0]["oneOf"])
        self.assertEqual(self.catalog_hits, 1)
        self.assertEqual(self.menu["create_task"]["inputSchema"]["required"], ["company", "revision"])

    def test_natural_assignment_returns_actual_saved_record_in_one_mcp_call(self):
        msg = {"jsonrpc": "2.0", "id": "task", "method": "tools/call",
               "params": {"name": "cosec_create_task", "arguments": self.args}}
        result = json.loads(m.respond(msg, self.desk)["result"]["content"][0]["text"])
        self.assertEqual(result["result"]["task"], self.task)
        self.assertIn("connector_ms", result)
        write = next(c for c in self.calls if c[0] == "create_task")
        self.assertEqual(write[1], {"company": "FASB", "revision": 17, "ownerId": "aisha",
                                    "serviceId": "standard-2", "quantity": 5, "dueDate": "2026-11-30"})
        self.assertEqual(write[2], self.args["request_id"])

    def test_resolved_write_is_stable_across_restart(self):
        self.call("create_task", self.args)
        self.calls.clear()
        self.revision = 18
        self.desk.journal = m.RequestJournal(self.path)
        self.call("create_task", self.args)
        self.assertEqual([c[0] for c in self.calls], ["create_task", "get_tasks"])
        self.assertEqual(self.calls[0][1]["revision"], 17)
        with self.assertRaisesRegex(m.ActionError, "different arguments"):
            self.call("create_task", {**self.args, "quantity": 7})

    def test_ambiguous_staff_cannot_create(self):
        self.people.append({"id": "another", "name": "Aisha Noor"})
        with self.assertRaisesRegex(m.ActionError, "unique"):
            self.call("create_task", self.args)
        self.assertNotIn("create_task", [c[0] for c in self.calls])

    def test_mine_uses_pinned_employee(self):
        self.assertEqual(self.call("get_tasks", {"mine": True})["tasks"][0]["task_id"], "other")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][1], {})
        self.assertEqual(self.call("get_tasks", {"mine": True, "task_id": "task-1"})["tasks"], [])

    def test_stale_review_remains_rejected(self):
        with self.assertRaisesRegex(m.ActionError, "409"):
            self.call("verify_task", {"company": "FASB", "taskId": "task-1", "revision": 16,
                                      "request_id": self.args["request_id"]})
        self.assertEqual([c[0] for c in self.calls], ["verify_task"])

    def test_timeout_after_commit_keeps_receipt(self):
        def execute(name, args, req, deadline):
            if name == "get_identity":
                raise m.ActionError("Timed out")
            return self.execute(name, args, req, deadline)
        self.desk.execute = execute
        result = self.call("set_widgets", {"widgets": [], "request_id": self.args["request_id"]})
        self.assertTrue(result["receipt"]["ok"])
        self.assertIn("Committed", result["readback"])
        self.assertEqual(len(self.calls), 1)

    def test_invalid_id_stops_before_writes(self):
        with self.assertRaisesRegex(m.ActionError, "UUID"):
            self.call("create_task", {**self.args, "request_id": "bad"})
        self.assertEqual(self.calls, [])

    def test_psql_is_pinned_and_errors_are_redacted(self):
        req = self.args["request_id"]
        deadline = time.monotonic() + 5
        result = subprocess.CompletedProcess([], 0, json.dumps({"request_id": req, "ticket": "a" * 64}), "")
        with patch.object(m.subprocess, "run", return_value=result) as proc:
            ticket = m.mint_ticket("get_tasks", {"company": "a'b"}, req, deadline)
            self.assertEqual(ticket["request_id"], req)
            sql = proc.call_args.kwargs["input"]
            self.assertIn("session_user = current_user", sql)
            self.assertIn("i.tasks_enabled", sql)
            self.assertIn("i.employee_id", sql)
            self.assertNotIn("a'b", sql)
        denied = subprocess.CompletedProcess([], 1, "", "sensitive test detail")
        with patch.object(m.subprocess, "run", return_value=denied):
            with self.assertRaisesRegex(m.ActionError, "^Ticket refused"):
                m.mint_ticket("get_tasks", {}, req, deadline)
        with patch.object(m.subprocess, "run") as proc, self.assertRaises(m.ActionError):
            m.mint_ticket("get_tasks", {}, req, time.monotonic() - 1)
        proc.assert_not_called()

    def test_stdio_handshake_ping_and_notification(self):
        messages = [{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                     "params": {"protocolVersion": "2025-06-18"}},
                    {"jsonrpc": "2.0", "method": "notifications/initialized"},
                    {"jsonrpc": "2.0", "id": 2, "method": "ping"}]
        proc = subprocess.run([sys.executable, str(SCRIPTS / "desk_mcp.py")],
                              input="".join(json.dumps(msg) + "\n" for msg in messages),
                              capture_output=True, text=True, check=True, timeout=5)
        replies = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual([r["id"] for r in replies], [1, 2])
        self.assertIn("tools", replies[0]["result"]["capabilities"])

if __name__ == "__main__":
    unittest.main()
