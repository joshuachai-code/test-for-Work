# Morning task list in G-Work

Import the [morning-brief skill folder](../morning-brief/) from GitHub, or upload [morning-brief.skill](../morning-brief.skill). Both include the required `SKILL.md` and the scheduling resources. The standalone [morning-brief.md](../morning-brief.md) is a readable reference, not the import package.

Each employee gets a **daily 9:00 a.m. Malaysia-time** briefing of live tasks, grouped by overdue, due today, upcoming, no deadline and awaiting review. It includes the existing dashboard task IDs and suggests what to start. The reminder itself does not change tasks. Use `--time 09:30` if that is the preferred start time.

## Activate in each employee's G-Work

1. Load the current SSM/CTC skills from this repository. Keep that employee's Neon connection pinned to their own restricted database login.
2. Find the employee's `run_sql` tool by capability, even if its connection has a custom name such as Hi2. Use the exact project context below on every SQL call. Ask G-Work to run `SELECT * FROM public.cosec_gwork_identity();` and confirm the returned employee is the signed-in staff member. Stop if unlinked or mismatched. Creating a schedule does not provision staff database access.
3. In that G-Work cowork session, run `python3 gwork/install-morning-briefing.py --staff-id <verified-ID> --staff-name '<verified-name>'` from this repository. The installer uses G-Work's built-in local scheduling API and reads back its result. Running it again updates that employee's existing reminder instead of making a duplicate. It stores no database password.
4. In G-Work **Scheduled Tasks**, select **Run now** once. Verify the staff identity, pending task IDs and dates against the dashboard. Address required permissions for the specific read tool if prompted. Keep the device timezone at Asia/Kuala_Lumpur and G-Work running at the scheduled time.

No reminder has been activated merely by downloading this repository. Without a G-Work session the installer stops without creating a task. The configured result appears in G-Work; no external notification channel is enabled.

## Find the employee's SQL tool and project

Discover tools by capability: search for `run_sql` (or `Neon SQL`) and inspect the server instructions. The connection may have a custom name such as **Hi2** or **Hi**. An empty MCP resources list does not mean SQL tools are unavailable. If the tool is disabled, enable this employee's restricted connection in G-Work's **Skills & Tools** picker and in the scheduled task's tool settings.

For this Cosec Desk deployment, pass this verified context on **every SQL call**, including identity checks and scheduled runs:

```json
{
  "project_id": "lingering-base-89796182",
  "branch_id": "br-super-thunder-az57jivk",
  "database_name": "neondb"
}
```

These are shared database routing identifiers, not credentials or an employee identity. Add the `sql` argument for the query. Preserve the connection's pinned restricted role: omit optional `role_name`; if the client requires a value, copy the exact pinned role stated in that server's instructions. Never infer it from a name or change it to access more data. Never send empty strings, JSON null or the string `"null"` for unused optional arguments; omit them, including `compute_id`.

Call SQL directly with this context; do not run `list_projects` or organization discovery first. **A G-Work organization ID is not a Neon organization ID.** An organization lookup error caused by the wrong ID does not establish that this configured project is inaccessible. If the direct SQL call fails with this exact context, report that specific failure and stop; do not switch to an owner connection or invent identifiers. A different deployment needs independently verified replacement context before use.

## Retry after a failed project lookup

Refresh/reimport the updated morning-brief folder or archive; an already installed copy does not become current merely because GitHub changed. In the employee's G-Work session, run the identity query directly with the context above. Require the expected active employee and Tasks enabled before creating or updating the reminder. Rerun the installer after a prompt update so an existing schedule also receives the corrected context; refreshing the skill alone does not rewrite a saved reminder.

For the existing Daniel demo connection only, Hi2 is pinned to `gwork_daniel`; its verified identity must be Daniel Tan, `leader-demo`. This is an example, not the role to assign to every employee. Other staff must use their own restricted connection. A failed organization lookup is not a reason to grant organization administration or database owner access.

## Shared task identity

`task_id` is the existing dashboard task's ID, not the G-Work conversation ID, recurring-reminder ID, skill `run_id` or Excel `job_id`. Starting an existing task updates it to **In progress**. Completing preparation submits that same task for review. Its company, deadline and assignee are retained. CTC uses the dashboard's **Certified true copies** service type. Fees, invoices and approval remain separate actions.

The database setup is maintained in [cosec-desk](https://github.com/joshuachai-code/cosec-desk/blob/main/scripts/migrations/gwork-task-sync.sql). Only provisioned staff connections can read or update permitted records; granting access to the reminder does not grant more database permissions.

Official scheduling reference: [G-Work Scheduled Tasks](https://www.gptbots.ai/docs/workspace/app-settings/scheduled-tasks).

## Explicit reviews after the briefing

A later direct request to verify or return an exact task uses the same restricted connection and `cosec_gwork_review_task(jsonb)`. It is separate from the automatic read-only briefing. Only an active Team Leader with Tasks and company/team access can review another person's submitted work; self-review and changed submissions are rejected. Linked records and Work history update atomically. See [the review procedure](task-review.md). Refresh the installed package, and update an existing saved reminder with the current installer if it should carry these follow-up instructions.
