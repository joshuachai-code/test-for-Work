# Save completed work to the shared database

## Connection and staff identity

Use the existing Neon SQL tool on Cosec Desk's production `neondb` database and configured branch. The connection must be pinned to the worker's restricted PostgreSQL login. The current Aisha pilot uses `gwork_member_a`; do not use that login for other staff. Do not select `neondb_owner` or ask the model to choose a database role. A G-Work login alone does not establish dashboard identity.

Use these installed functions:

- `public.cosec_gwork_identity()` — returns only the active staff identity linked to this database connection and whether Tasks is enabled.
- `public.cosec_gwork_record_completion(jsonb)` — creates or submits the linked worker's own preparation task, with current company and section checks, an audit record and duplicate protection.
- `public.gwork_tasks` — reads current permitted tasks. It remains a read-only view.

Before saving, run:

```sql
SELECT * FROM public.cosec_gwork_identity();
SELECT current_user, current_setting('transaction_read_only') AS transaction_read_only;
```

Require the linked employee to be the worker doing this run, Tasks enabled and the expected restricted login. An empty identity result means the account/link is inactive or unconfigured. Do not pass a user ID, staff role or approver as a way to change identity. The server derives the actor from the authenticated database login and checks current dashboard permissions on every call.

The Neon connection must permit read/write transactions for the save function. If the MCP connection is configured with `readonly=true`, it still blocks saves even though the function is callable. Report the block and have the administrator enable writes **while keeping the same restricted role pin**. Do not remove the role pin or broaden table privileges. The save action does not grant direct writes to companies, tasks, accounts or raw workspace tables. These instructions do not themselves edit the installed G-Work connection.

## Match the company and task

Read permitted company rows and match the legal name, confirmed company code and registration number. A group ID alone is insufficient. Read `public.gwork_tasks` for that company; prefer the task ID already associated with this job. Resolve multiple candidate tasks rather than choosing an unrelated one.

Use a preparation task owned by the authenticated worker. This action cannot submit another employee's task, complete a linked document or statutory milestone, approve work, issue an invoice or modify rates. A directory-only Allow viewing rule is not permission to work for that company. If an existing task includes signing, lodgement or other unfinished obligations, use a separate preparation task when authorized. Existing tasks linked through `document_id` or a filing milestone must use the dashboard workflow instead.

Use one stable run ID and one SHA-256 digest for the checked output/evidence manifest. Save the exact request and returned task ID in a local completion receipt without credentials. Do not regenerate the run ID for a retry. SSM uses the finished form's SHA-256; CTC uses the SHA-256 of the saved, checked per-run evidence manifest described in its SKILL.md.

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

For CTC use `"skill":"ctc-billing"`. To submit an existing eligible task, add its exact `task_id`; omit `title` unless already included in the original request. New tasks are assigned to the authenticated worker and require the worker to belong to the company's team. Do not include `ownerId`, `status`, `invoice`, `rate`, `milestoneKey` or other undocumented fields; they are rejected.

Limits: `title` up to 160 characters; `note` 1–2,000 characters; `run_id` up to 128 ASCII letters/digits/dots/underscores/colons/hyphens, starting with a letter or digit. Use the actual completion date in Asia/Kuala_Lumpur, never a future date or the document's signing/lodgement date. Do not truncate essential references to fit.

Put the run ID, output filename or manifest reference, digest, document-check outcome and outstanding human actions in `note`. Include real saved file paths or existing permission-controlled durable URLs, labelled accurately. Do not make files public to obtain a link. A path is not a cloud upload or binary attachment. Keep identity-document details, field ledgers, credentials and detailed CTC financial values out of task notes; retain them in authorized evidence/record books.

The function atomically saves the task as `submitted`, records the linked employee as submitter, updates the workspace revision and writes an audit event. It creates no invoice and performs no Team Leader approval. Retain the returned `task_id`, `assigned_staff_id`, `status`, `completed_date`, `completion_note`, `run_id`, `output_sha256`, `revision` and `already_recorded` in the local receipt.

## Read back and recover safely

Make a fresh query for the exact company/task in `public.gwork_tasks`. Check assignee, completion date, note and current status against the result. The note must identify the run/digest. When role reporting hides a just-submitted task (currently Directors), replay the **identical original request**: `already_recorded:true` confirms the persisted receipt and returns the task's current status without changing it. Do not change a request lacking `task_id` by adding the returned ID on replay; keep the exact original fields.

A timeout may occur after a successful commit. Read back first; if necessary, replay only the identical request. The database serializes writes and returns the existing receipt instead of duplicating tasks, audit events or submissions. Reusing a run ID with different content is rejected. Never switch identities or create a fresh run ID just to retry.

A later Team Leader verification or return must be preserved. A replay reports the current status; it does not submit again. Returned work requires correction, a newly checked evidence hash and a new run ID before resubmission. A task reassigned to another employee or a newly hidden company is no longer writable, including receipt replay.

For a read-only transaction, missing function/grant, disabled account, missing Tasks access, inaccessible company or another person's task, preserve the files and receipt and report the actual block. Do not grant permissions or write raw `app_desk` JSON. For an uncertain outcome, report `pending_unknown`; for a checked result, report `saved_and_checked` with company/task/status. File delivery success and database save success are separate outcomes.

The production dashboard is `https://cosec-desk.vercel.app`. It normally checks every six seconds and pauses applying updates while editing or showing a dialog. A reload reads current permitted records. Old G-Work replies do not update automatically; make a new query. Director task reports currently exclude submitted/returned work until the existing review rules permit it. Do not claim every role immediately sees a submitted task.
