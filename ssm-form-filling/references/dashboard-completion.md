# Save completed work to the shared database

## Connection and staff identity

Use the existing Neon SQL tool on Cosec Desk's production `neondb` database and configured branch. The connection must be pinned to the worker's restricted PostgreSQL login. The current Aisha pilot uses `gwork_member_a`; do not use that login for other staff. Do not select `neondb_owner` or ask the model to choose a database role. A G-Work login alone does not establish dashboard identity.

Use these installed functions:

- `public.cosec_gwork_identity()` — returns only the active staff identity linked to this database connection and whether Tasks is enabled.
- `public.cosec_gwork_start_task(jsonb)` — starts the worker's existing preparation task using its dashboard `task_id`.
- `public.cosec_gwork_record_completion(jsonb)` — creates or submits the linked worker's own preparation task, with current company and section checks, an audit record and duplicate protection.
- `public.gwork_task_details` — reads current permitted tasks, including `task_id`, deadline, status, task type and workflow. `public.gwork_tasks` remains available for older clients. Both are read-only views.

### Known assignment

When the worker selects a known company and task, one scoped read checks identity, transaction mode and the selected assignment together. Use it for the current preflight or fresh read-back; select the evidence fields required for the stage. Bind the configured login, expected linked staff ID, company code and exact task ID respectively. For a SQL-string-only tool use a safely encoded UTF-8 hex literal per value as described below. Never interpolate user text.

```sql
WITH linked AS (
  SELECT i.*, count(*) OVER () AS links FROM public.cosec_gwork_identity() AS i
)
SELECT i.employee_id, i.staff_role, current_setting('transaction_read_only') AS read_only,
       t.company_code, t.company_name, t.task_id, t.title, t.status, t.assigned_staff_id,
       t.due_date, t.workflow, t.service_id, t.document_id, t.milestone_key,
       t.completed_date, t.completion_note
FROM linked AS i LEFT JOIN public.gwork_task_details AS t
  ON t.company_code = $3 AND t.task_id = $4 AND t.assigned_staff_id = i.employee_id
WHERE i.links = 1 AND i.tasks_enabled AND i.database_role = current_user
  AND i.database_role = $1 AND i.employee_id = $2;
```

Require the expected staff role and one matching assignment. Zero rows means identity or Tasks access failed; a null task ID means the assignment is unavailable to this worker. Neither permits a write. When the legal identity/code is already established against the company record, skip repeating the directory search. Keep a fresh read after each write and after a user handoff before a new write. Do not reuse an old status across a confirmation pause. A narrow mutation still rechecks permission on the server.

### Standalone work or unknown assignment

When company or task matching is still needed, first run:

```sql
SELECT * FROM public.cosec_gwork_identity();
SELECT current_user, current_setting('transaction_read_only') AS transaction_read_only;
```

Require the linked employee to be the worker doing this run, Tasks enabled and the expected restricted login. An empty identity result means the account/link is inactive or unconfigured. Do not pass a user ID, staff role or approver as a way to change identity. The server derives the actor from the authenticated database login and checks current dashboard permissions on every call.

The Neon connection must permit read/write transactions for the save function. If the MCP connection is configured with `readonly=true`, it still blocks saves even though the function is callable. Report the block and have the administrator enable writes **while keeping the same restricted role pin**. Do not remove the role pin or broaden table privileges. The save action does not grant direct writes to companies, tasks, accounts or raw workspace tables. These instructions do not themselves edit the installed G-Work connection.

## Match the company and task

For an unresolved company, read permitted company rows and match the legal name, confirmed company code and registration number. A group ID alone is insufficient. Read `public.gwork_task_details` for that company. A task selected from the morning briefing must retain that exact `task_id`; never replace it with a new task. A conversation ID, workflow run ID, Excel job ID or title is not a dashboard task ID. Resolve multiple candidate tasks rather than choosing an unrelated one. Preserve the existing deadline, assignee and task type.

Use a preparation task owned by the authenticated worker. This action cannot submit another employee's task, complete a linked document or statutory milestone, approve work, issue an invoice or modify rates. A directory-only Allow viewing rule is not permission to work for that company. If an existing task includes signing, lodgement or other unfinished obligations, use a separate preparation task when authorized. For tasks linked through `document_id` or a milestone, use the shared dashboard actions described in [dashboard-actions.md](dashboard-actions.md). They support starting/submitting the same task and authorized review. Submit only after the entire linked obligation is actually fulfilled; a prepared draft alone is not statutory lodgement or certification.

Use one stable run ID and one SHA-256 digest for the checked output/evidence manifest. Save the exact request and returned task ID in a local completion receipt without credentials. Do not regenerate the run ID for a retry. SSM uses the finished form's SHA-256; CTC uses the SHA-256 of the saved, checked per-run evidence manifest described in its SKILL.md.

## Start the selected task before working

Once the worker asks to start an existing, eligible preparation task, call:

```sql
SELECT public.cosec_gwork_start_task($1::jsonb) AS result;
```

The request has only `skill` (`ctc-billing` or `ssm-form-filling`), `company_code` and the exact existing `task_id`. Use the bound-parameter or validated hexadecimal approach described below, with this function name. Read back that same ID in `public.gwork_task_details` and confirm `in_progress`, the assignee and unchanged deadline. An identical start retry returns `already_started:true` without another start event. It cannot reopen a submitted or verified task. A failed start must be disclosed; do not claim the dashboard shows work in progress.

The morning reminder is read-only: it must not start or submit tasks automatically. Start only after the worker chooses work. If no matching dashboard task exists, say that clearly; an authorized new preparation task may receive its database-generated ID when saved at completion. Never invent an ID or silently create another task for existing work.

CTC uses the dashboard service linked to `ctc-billing` (currently **Certified true copies**, service ID `standard-2`). The database resolves that mapping centrally, so a service rename retains its identity. Reject a CTC run against an unrelated task type, and reject an SSM run against a CTC task. For an existing untyped CTC preparation task, the server adds the CTC type. This classification does not change agreed quantities/prices, approve charges or issue an invoice; a newly classified unpriced task remains unpriced.

## Save with the narrow completion function

Call `run_sql` with this SQL shape and the actual JSON request:

```sql
SELECT public.cosec_gwork_record_completion($1::jsonb) AS result;
```

Use a bound parameter when supported. If the SQL tool accepts only a SQL string, serialize the request with a JSON library, encode those UTF-8 bytes as hexadecimal and verify that the result contains only `[0-9a-f]`. Emit `SELECT public.cosec_gwork_record_completion(convert_from(decode('<validated hex>','hex'),'UTF8')::jsonb) AS result;`. This keeps company names, notes, paths and document text out of SQL syntax. Do not concatenate raw data into SQL or rely on an unchecked dollar-quote delimiter.

Request for a new preparation task:

```json
{
  "skill": "ssm-form-filling",
  "run_id": "<stable run ID>",
  "company_code": "<confirmed company code>",
  "title": "Prepare <form or CTC package> — <period/job reference>",
  "completed_date": "<actual preparation completion date YYYY-MM-DD>",
  "note": "<checked result and output references>",
  "output_sha256": "<64-character lowercase SHA-256>"
}
```

For CTC use `"skill":"ctc-billing"`. To submit an existing eligible task, supply the exact `task_id` selected and started earlier; omit `title` unless already included in the original request. For new work without an existing task, the server creates a unique `task_id`; preserve the returned ID for later work. New tasks are assigned to the authenticated worker and require the worker to belong to the company's team. An unfinished matching CTC task prevents ID-less creation: use its existing ID. Do not include `ownerId`, `status`, `invoice`, `rate`, `milestoneKey` or other undocumented fields; they are rejected.

Limits: `title` up to 160 characters; `note` 1–2,000 characters; `run_id` up to 128 ASCII letters/digits/dots/underscores/colons/hyphens, starting with a letter or digit. Use the actual completion date in Asia/Kuala_Lumpur, never a future date or the document's signing/lodgement date. Do not truncate essential references to fit.

Put the run ID, output filename or manifest reference, digest, document-check outcome and outstanding human actions in `note`. Include real saved file paths or existing permission-controlled durable URLs, labelled accurately. Do not make files public to obtain a link. A path is not a cloud upload or binary attachment. Keep identity-document details, field ledgers, credentials and detailed CTC financial values out of task notes; retain them in authorized evidence/record books.

The function atomically saves the task as `submitted`, records the linked employee as submitter, updates the workspace revision and writes an audit event. It creates no invoice and performs no Team Leader approval. Retain the returned `task_id`, `assigned_staff_id`, `status`, `completed_date`, `completion_note`, `run_id`, `output_sha256`, `revision` and `already_recorded` in the local receipt.

## Read back and recover safely

Make a fresh query for the exact company/task in `public.gwork_task_details`. Check the same `task_id`, unchanged deadline, assignee, task type, completion date, note and current status against the result. For CTC, verify `service_id` is the dashboard's CTC service and `workflow` is `ctc-billing`. The note must identify the run/digest. When role reporting hides a just-submitted task (currently Directors), replay the **identical original request**: `already_recorded:true` confirms the persisted receipt and returns the task's current status without changing it. Do not change a request lacking `task_id` by adding the returned ID on replay; keep the exact original fields.

A timeout may occur after a successful commit. Read back first; if necessary, replay only the identical request. The database serializes writes and returns the existing receipt instead of duplicating tasks, audit events or submissions. Reusing a run ID with different content is rejected. Never switch identities or create a fresh run ID just to retry.

A later Team Leader verification or return must be preserved. A replay reports the current status; it does not submit again. Returned work requires correction, a newly checked evidence hash and a new run ID before resubmission. A task reassigned to another employee or a newly hidden company is no longer writable, including receipt replay.

For a read-only transaction, missing function/grant, disabled account, missing Tasks access, inaccessible company or another person's task, preserve the files and receipt and report the actual block. Do not grant permissions or write raw `app_desk` JSON. For an uncertain outcome, report `pending_unknown`; for a checked result, report `saved_and_checked` with company/task/status. File delivery success and database save success are separate outcomes.

The production dashboard is `https://cosec-desk.vercel.app`. It normally checks every six seconds and pauses applying updates while editing or showing a dialog. A reload reads current permitted records. Old G-Work replies do not update automatically; make a new query. Director task reports currently exclude submitted/returned work until the existing review rules permit it. Do not claim every role immediately sees a submitted task.
