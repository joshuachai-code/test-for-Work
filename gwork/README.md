# All dashboard actions in G-Work

Import [cosec-desk-actions](../cosec-desk-actions/) for the full dashboard action menu. The current morning-brief, CTC and SSM packages also bundle the same client and instructions. Refresh an already installed package once; a GitHub update does not update its cached G-Work copy. Continue using the employee’s existing restricted Hi/Hi2 connection; no new OAuth sign-in is required. The live action menu is https://cosec-desk.vercel.app/api/gwork and uses the dashboard’s actual handlers and current permissions.

For a live demo, refresh the four imports from the same revision. A member or leader can ask “Any updates on my tasks for Fast AI Sdn Bhd?” from any of them. The known-company status path uses one scoped ticket and one dashboard read. To apply the faster daily briefing to a reminder that already exists, rerun the morning-brief installer in its owner’s G-Work session with the same verified staff ID and scheduled time. It updates that reminder in place.

## Connect Cosec Desk as an MCP server

The local server exposes each operation in the live dashboard catalog as a typed `cosec_*` tool. It handles identity checks, action tickets and fresh reads inside the tool call. Routine task creation, reassignment, starting, guidance and company assignment can resolve supplied names or codes and fetch the current revision internally. Actions that depend on a previously reviewed state still require its revision. Never fill a missing review, human decision or quantity from a default.

1. Check out this revision on the employee's computer. Install Python 3.9+ and the PostgreSQL `psql` client. Make sure the G-Work subprocess can find `psql` on its PATH.
2. Configure a private PostgreSQL service for this employee's **existing restricted Neon login**, with the provisioned database, host, port, `sslmode=verify-full` and a trusted CA root. Supply the password through libpq's private password file. Test that service with `psql` as the employee. A Hi/Hi2 connection managed entirely by G-Work does not automatically provide libpq credentials. Leave the existing connection in use until this employee's service is provisioned.
3. In [G-Work Tool Management](https://www.gptbots.ai/docs/workspace/app-settings/tools), add a **local stdio MCP**. Substitute the absolute interpreter and checkout paths and the verified identity for this employee. Enable it on that employee's account. The environment below is an example for Daniel.

```json
{
  "mcpServers": {
    "cosec-desk": {
      "command": "/absolute/path/to/python3",
      "args": ["/absolute/path/to/test-for-Work/cosec-desk-actions/scripts/desk_mcp.py"],
      "env": {
        "PGSERVICE": "cosec-daniel",
        "COSEC_DB_ROLE": "gwork_daniel",
        "COSEC_EMPLOYEE_ID": "leader-demo",
        "PATH": "/absolute/directory/containing/psql:/usr/bin:/bin"
      }
    }
  }
}
```

4. Refresh the cosec-desk-actions folder or its standalone archive from this revision for dashboard commands. Specialist packages continue to handle document work. Confirm the tools list, then run the read-only prompt “Show my tasks for FASB”. Check the returned rows under that employee. Task, billing, staff and handover permissions continue to come from Cosec Desk. If enabling tools for a saved schedule, check the schedule's own tool selection and existing reporting instructions.

For changes that time out, use the original UUID and inputs to reconcile. The local journal retains the resolved company, assignee, service and revision for those routine actions so it can retry after a restart. Keep the journal on that employee's computer. A completed replay can have a minimal receipt. Report only the fields supplied by a fresh permitted read. A 409 requires reviewing the changed state before issuing a new request ID.

Measure from Send to the final answer, with the tool's `connector_ms` recorded separately. Benchmark each operation in a disposable test workspace with the appropriate actor, both on a fresh session and a repeated one. The connector carries a 22-second I/O budget to leave time for the model. A timeout, a clarification, or a queued document job does not establish successful completion within 30 seconds.

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
  "database_name": "neondb",
  "compute_id": "ep-fragrant-dust-az3a8wul"
}
```

These are shared database routing identifiers, not credentials or an employee identity. Add the `sql` argument for the query. Preserve the connection's pinned restricted role: omit optional `role_name`; if the client requires a value, copy the exact pinned role stated in that server's instructions. Never infer it from a name or change it to access more data. Include the verified `compute_id` above on every call. Never send an empty string, `?`, JSON null, the string `"null"`, or the branch ID as the compute ID. Neon maps `compute_id` to `endpoint_id`; a validation error here can be caused by malformed tool arguments before authentication. If a previous call used one of those invalid values, correct it to `ep-fragrant-dust-az3a8wul` and retry the identity check once; do not guess another endpoint or ask for reauthorization solely because malformed arguments were rejected. Omit other unused optional arguments instead of sending placeholders.

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
