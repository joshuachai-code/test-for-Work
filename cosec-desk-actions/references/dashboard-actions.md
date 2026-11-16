# Dashboard actions through the restricted connection

## Connection and identity

Find the employee's existing Neon `run_sql` tool (it may be named Hi2 or Hi). Use this context on every SQL call:

```json
{"project_id":"lingering-base-89796182","branch_id":"br-super-thunder-az57jivk","database_name":"neondb","compute_id":"ep-fragrant-dust-az3a8wul"}
```

Add `sql`. Include the verified `compute_id` on every call, including identity checks. It is a database routing identifier, not a credential or staff identity. Never send an empty string, `?`, `null`, or the branch ID as the compute ID. Neon maps this field to `endpoint_id`; an endpoint-ID validation error can mean malformed tool arguments, not a broken login. If a previous call used an invalid value, correct it to this verified value and retry the identity check once. If that exact context still fails, stop and report the error without inventing another endpoint.

Preserve the server's pinned role. Omit optional `role_name`; if G-Work requires it, copy the exact pinned role from that server's instructions (Daniel's Hi2: `gwork_daniel`). Never fill it with an empty string or change roles. Other employees must retain their own pinned role. Do not run organization/project discovery first or use a G-Work organization ID as a Neon organization ID.

Run `SELECT current_user AS database_login, i.* FROM public.cosec_gwork_identity() AS i;`. Require exactly one linked active employee matching the expected person. For task actions, Tasks must be enabled. Daniel's Hi2 should identify `gwork_daniel` / `leader-demo`; this is not the identity for other employees. Stop on a mismatch.

## Discover, read, then act

1. From this installed package, run `python3 scripts/dashboard_action.py menu` (or `menu create_task`, etc.). This GET is public capability documentation, not company data. Read the exact schema needed. Operations cover tasks, documents/register/annual/quarterly/board/company records, company briefs, assignments, billing, staff access, handovers, preferences and work history. Password changes and sign-in remain in Account settings.
2. Use `get_identity` for staff/section details and colleagues; `get_workspace` for permitted records, task types and `revision`; `get_directory` for legal company names/codes; `get_tasks` for task IDs/states. These read operations use the same ticket procedure below. A directory match alone does not grant work access. Match registration numbers where available; a group ID is not a company code.
3. For a write, include a fresh `revision` when required. Select only intended fields. Do not invent deadlines, quantities, evidence or prices. CTC uses the existing **Certified true copies** service from `rates` (currently `standard-2`). Creating a CTC task makes it OPEN, not completed, certified, invoiced or submitted.
4. Prepare a private JSON request file using a JSON library:

```json
{"operation":"create_task","arguments":{"revision":123,"company":"FASB","title":"Prepare CTC for Fast AI Sdn Bhd","ownerId":"member-demo","serviceId":"standard-2"}}
```

This is an example only: replace revision/company/assignee/service using fresh reads. Preserve `TESTING` if a separate CTC task was requested. Do not execute example mutations during setup.

5. Run `python3 scripts/dashboard_action.py prepare --request /private/path/request.json`. It adds a UUID `request_id` once to that file and prints complete `run_sql` arguments with safely encoded JSON. Send those arguments to the verified restricted SQL tool. Function: `public.cosec_gwork_request(request_id uuid, operation text, input jsonb)`. It returns a short-lived ticket bound to this employee and exact action. **Issuing a ticket does not execute the action.**
6. Feed the SQL result as JSON on stdin to `python3 scripts/dashboard_action.py execute --receipt /private/path/receipt.json`. It accepts the `{request_id,ticket,...}` object or JSON-wrapped SQL results. Use stdin or a private temporary file, never a ticket in a URL/command argument/final response. The client sends only `request_id` and `ticket` to the fixed production HTTPS endpoint and rejects redirects. It needs no DB/dashboard password, browser session or local scheduling API.
7. Make a **new read request** for the exact records/settings changed. Confirm ID/status/assignee and relevant fields. Dashboard polling normally displays changes within about six seconds when not editing; reload reads the current result. Old G-Work messages do not update themselves.

The server rechecks the linked employee, active state, role, sections, company/team scope and workflow state at execution time. These are server checks, not prompt rules. Operation and receipt commit together. Changes use `source=gwork` in the common audit history.

## Retry without duplicate work

- Keep the original request file, ID and arguments until verified. Reuse them after timeout/5xx. Re-running `prepare` preserves the ID; reissue its ticket through the same restricted connection if expired. Never generate a new ID merely because a response was lost.
- `already_completed:true` means that request already executed; it never repeats the mutation or replays old sensitive records. Read fresh to verify current state. For a completed read, issue a new read ID to retrieve data.
- A 409 means the workspace changed before execution. Re-read, review whether the intended change is still appropriate, then use a new ID with the new revision. Never automatically repeat a review against a changed submission.
- For 401/403, report the actual block. Never switch identities, remove the pin, grant raw table writes, or fall back to an owner/browser session.
- Delete ticket files immediately after use. Keep result receipts without credentials. Delete a staff-creation input containing an initial password after success; do not echo it in chat or ask for the user's current password.

## Editing and workflow boundaries

`edit_records` takes `revision` plus JSON-pointer patches from a fresh scoped workspace. It uses dashboard Save rules: Director company setup, authorized Leader records, assigned Member document preparation and enabled sections. Use exact field names. Arrays use the current index or `/-` for addition; generate UUIDs for new document/board rows. Never patch tasks, completions, assignments or financial records to bypass their dedicated actions. Linked documents/milestones use `start_task`/`submit_task` then authorized review.

CTC/SSM outputs must pass preparation checks and file saves before submission. Do not complete a statutory milestone for a draft alone. If a task includes unfinished signing/lodgement/certification, keep it unfinished and use a separately authorized preparation task. Files remain in approved storage; a task note/path is not a binary attachment or proof of cloud sync.

Company access: `hide` blocks work; `show` grants directory visibility only; `inherit` follows assignments. Only Directors change these rules. Team Leaders review another person's submitted work in their team, never their own. Members start/submit only their own work. `transfer_handover` assigns a package; the recipient's `accept_handover` adds its pending tasks to their current workload.

Invoices require an explicit Director instruction. Read `get_billing` for the company and copy its exact current `draft_lines` into `issue_invoice`; do not calculate or guess them. Recording an invoice does not send it. CTC/SSM preparation never authorizes an invoice automatically.
