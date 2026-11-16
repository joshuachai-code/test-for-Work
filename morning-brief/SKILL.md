---
name: morning-brief
description: Set up or run a daily G-Work morning briefing from the live Cosec Desk database. Show the linked employee's pending tasks, deadlines and existing task IDs. Use for morning work lists, overdue-task checks and daily reminders at 9 or 9:30 a.m. Malaysia time.
---

# Morning brief

Use the live database behind https://cosec-desk.vercel.app as the source of truth. Keep the briefing read-only. Do not start, create, submit, reassign or approve dashboard tasks, change deadlines, or run CTC/SSM work during a briefing.

## Verify the employee

Use the employee's existing restricted Neon connection and its configured project/branch. Run `SELECT * FROM public.cosec_gwork_identity();` and verify exactly one active linked identity, Tasks enabled and the expected staff member. A G-Work login alone does not establish database identity. Stop if the connection is missing, unlinked or mismatched. Never choose an owner role, another employee connection or a guessed project/branch. Never request or store database passwords in this package.

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
3. The installer reads [references/morning-briefing-prompt.md](references/morning-briefing-prompt.md), binds the verified employee, checks the device's UTC+8 timezone and uses G-Work's local scheduling API. It updates an existing reminder instead of duplicating it, enables no external notification channel, and reads back the saved configuration.
4. If the script cannot run because this is not a G-Work cowork session or its local scheduling API is unavailable, report that no schedule was created. If G-Work's native Scheduled Tasks capability is available instead, create/update the same employee-specific reminder with the fully bound prompt: daily at the selected time, Asia/Kuala_Lumpur device timezone, fresh session per run, no expiry and no external notification channel. Check existing reminders first, and verify the saved configuration before claiming success.
5. Run the reminder once in G-Work and compare the returned task IDs/deadlines with the dashboard. Handle any tool-permission prompt for the specific read tool through the platform's normal controls. Keep the G-Work app running on the device at the scheduled time. Distinguish a verified saved schedule from a successfully tested run.

## Keep the same task identity

The database `task_id` is the dashboard task's existing ID. It is different from the G-Work conversation ID, recurring-reminder ID, skill `run_id` and Excel `job_id`. Preserve it exactly.

When the employee later chooses a task to work on, use the separately installed CTC or SSM workflow, re-read permissions and status, and update that same task through `public.cosec_gwork_start_task(jsonb)` and, after verified preparation, `public.cosec_gwork_record_completion(jsonb)`. Preserve its deadline and assignee. CTC uses the dashboard's mapped **Certified true copies** service. Linked document/statutory tasks follow the dashboard workflow. This package does not include or replace the CTC/SSM workflows and does not authorize approvals, invoices or SSM lodgement.
