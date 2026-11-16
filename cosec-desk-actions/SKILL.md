---
name: cosec-desk-actions
description: Read and perform Cosec Desk dashboard actions from G-Work using the linked employee's current permissions. Use for task creation, assignment, starting, submission, verification, returns, company/document/register/board updates, handovers, task billing, staff settings, company access and work history, including action requests after a morning briefing. Keeps the same live database and task IDs as the dashboard.
---

# Cosec Desk actions

Use the live dashboard action service at `https://cosec-desk.vercel.app/api/gwork`. It runs the same handlers and permission checks as the dashboard. Do not infer that task creation or other writes are unavailable just because Hi/Hi2 exposes only `run_sql` or because an earlier briefing was read-only. The restricted SQL connection authorizes an exact action; the bundled HTTP client executes it. No browser session or new OAuth connection is needed.

Follow [references/dashboard-actions.md](references/dashboard-actions.md) for the complete procedure. Read the current operation menu using `python3 scripts/dashboard_action.py menu`; the server supplies the current argument schemas, so never guess function or field names.

Preserve the employee's pinned restricted database role. First verify the linked identity and expected person. Never select an owner connection or another employee role, trust a supplied staff ID as authentication, or modify permissions to make an action pass.

Complete only the work the user requested. A briefing remains read-only. A later explicit request to create, assign, submit, review or otherwise update work is a separate authorized action. Starting a task does not complete it; completion requires actual work/evidence; verification is the Team Leader's review; billing is a separate Director action. Do not perform statutory lodgement, certification, signing, invoice delivery or payment collection merely because a task was saved.

Use the CTC/SSM workflows for preparing and checking actual outputs. Retain the existing `task_id`, company, assignee and deadline. A new task gets its ID from the server. After every write, make a fresh permitted read and report the saved ID/status. Never claim success from an issued ticket alone.
