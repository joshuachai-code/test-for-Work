---
name: morning-brief
description: Set up or run a daily G-Work morning briefing from the live Cosec Desk database. Show the linked employee's pending tasks, deadlines and existing task IDs. Use for morning work lists, overdue-task checks, daily reminders at 9 or 9:30 a.m. Malaysia time, and explicit Team Leader review requests after a briefing.
---

# Morning brief

For general dashboard actions—including creating or assigning tasks, reviews, record updates and handovers—use [references/dashboard-actions.md](references/dashboard-actions.md) and the bundled `scripts/dashboard_action.py`. This uses the existing restricted SQL connection plus the live dashboard API, so it does not need a browser or new OAuth setup. Read the server action menu instead of assuming an operation is missing. Keep scheduled briefings read-only; act on later explicit requests separately.

Use the live database behind https://cosec-desk.vercel.app as the source of truth. Keep the briefing itself read-only. Do not start, create, submit, reassign or approve dashboard tasks, change deadlines, or run CTC/SSM work during a briefing. A later direct user request to create, assign, start, submit, verify, return or otherwise update work is a separate action: follow [references/dashboard-actions.md](references/dashboard-actions.md) instead of refusing because this chat began with a briefing.

## Find the employee's SQL tool and project

Discover tools by capability: search for `run_sql` (or `Neon SQL`) and inspect the server instructions. The connection may have a custom name such as **Hi2** or **Hi**. An empty MCP resources list does not mean SQL tools are unavailable. If the tool is disabled, enable this employee's restricted connection in G-Work's **Skills & Tools** picker and in the scheduled task's tool settings.

For this Cosec Desk deployment, pass this verified context on **every SQL call**, including identity checks and scheduled runs:

```json
{
  "project_id": "lingering-base-89796182",
  "branch_id": "br-super-thunder-az57jivk",
  "database_name": "neondb",
  "compute_id": "ep-fragrant-dust-az3a8wul"
}
```

These are shared database routing identifiers, not credentials or an employee identity. Add the `sql` argument for the query. Preserve the connection's pinned restricted role: omit optional `role_name`; if the client requires a value, copy the exact pinned role stated in that server's instructions. Never infer it from a name or change it to access more data. Include the verified `compute_id` above on every call. Never send an empty string, `?`, JSON null, the string `"null"`, or the branch ID as the compute ID. Neon maps `compute_id` to `endpoint_id`; a validation error here can be caused by malformed tool arguments before authentication. If a previous call used one of those invalid values, correct it to `ep-fragrant-dust-az3a8wul` and retry the identity check once; do not guess another endpoint or ask for reauthorization solely because malformed arguments were rejected. Omit other unused optional arguments instead of sending placeholders.

Call SQL directly with this context; do not run `list_projects` or organization discovery first. **A G-Work organization ID is not a Neon organization ID.** An organization lookup error caused by the wrong ID does not establish that this configured project is inaccessible. If the direct SQL call fails with this exact context, report that specific failure and stop; do not switch to an owner connection or invent identifiers. A different deployment needs independently verified replacement context before use.

## Verify the employee

Use the employee's existing restricted Neon connection with the exact project context above. Run `SELECT current_user AS database_login, i.* FROM public.cosec_gwork_identity() AS i;` and verify exactly one active linked identity, Tasks enabled and the expected staff member. A G-Work login alone does not establish database identity. Stop if the connection is missing, unlinked or mismatched. Never choose an owner role, another employee connection or a guessed project/branch. Never request or store database passwords in this package.

For a scheduled run, require the verified employee ID to match the ID bound into that reminder. Recheck permissions on every run. For a one-off briefing, verify the current linked employee before reading tasks.

## Run the briefing now

Read [references/morning-briefing-prompt.md](references/morning-briefing-prompt.md). Replace every `__STAFF_ID__` and `__STAFF_NAME__` using the verified identity, then follow the full prompt. Do not execute unresolved placeholders.

Read `public.gwork_task_details` for the current permitted tasks. Use the database's current date in Asia/Kuala_Lumpur to group own actionable work into overdue, due today, due in the next seven days, later and no/invalid deadline. Keep submitted work in waiting-for-review. Team Leaders get a separate permitted team review/follow-up list; Directors retain the database's existing review visibility rules. Show the exact `task_id`, company, task type/title, status, deadline and suggested next action, with the time checked. Suggest at most three tasks to start; do not start them automatically. A failed read is not an empty task list.

## Create or update a recurring reminder

Only create or change a schedule when requested. Default to **daily at 09:00 Asia/Kuala_Lumpur**; use **09:30** if requested. Importing this skill alone does not activate a schedule.

1. Verify the staff identity as above. Use that returned ID and name when installing; never hardcode the Aisha pilot for another employee.
2. From this installed skill's directory, run the bundled installer in the employee's G-Work cowork session:

   ```bash
   python3 scripts/install-morning-briefing.py --staff-id <verified-ID> --staff-name '<verified-name>'
   ```

   Replace the placeholders with actual values. Use structured process arguments or proper shell quoting for names; never execute untrusted text as shell syntax. Add `--time 09:30` if requested. `--dry-run` only prepares configuration and does not activate a reminder.
3. The installer reads [references/morning-briefing-prompt.md](references/morning-briefing-prompt.md), embeds the project context above and binds the verified employee, checks the device's UTC+8 timezone and uses G-Work's local scheduling API. It updates an existing reminder instead of duplicating it, enables no external notification channel, and reads back the saved configuration.
4. If the script cannot run because this is not a G-Work cowork session or its local scheduling API is unavailable, report that no schedule was created. If G-Work's native Scheduled Tasks capability is available instead, create/update the same employee-specific reminder with the fully bound prompt: daily at the selected time, Asia/Kuala_Lumpur device timezone, fresh session per run, no expiry and no external notification channel. Check existing reminders first, and verify the saved configuration before claiming success.
5. Ensure the employee's restricted SQL tool is enabled for the scheduled run; a tool available only in the setup chat is not evidence of scheduled access. Run the reminder once in G-Work and compare the returned task IDs/deadlines with the dashboard. Handle any tool-permission prompt for the specific read tool through the platform's normal controls. Keep the G-Work app running on the device at the scheduled time. Distinguish a verified saved schedule from a successfully tested run.

## Keep the same task identity

The database `task_id` is the dashboard task's existing ID. It is different from the G-Work conversation ID, recurring-reminder ID, skill `run_id` and Excel `job_id`. Preserve it exactly.

When the employee later chooses a task to work on, use the separately installed CTC or SSM workflow, re-read permissions and status, and update that same task through `public.cosec_gwork_start_task(jsonb)` and, after verified preparation, `public.cosec_gwork_record_completion(jsonb)`. Preserve its deadline and assignee. CTC uses the dashboard's mapped **Certified true copies** service. Linked document/statutory tasks follow the dashboard workflow. This package does not include or replace the CTC/SSM workflows. Team Leader review requires a separate explicit user request and the checks in references/task-review.md. Neither briefing nor review issues invoices or performs SSM lodgement.
