# Morning task list in G-Work

Import the [morning-brief skill folder](../morning-brief/) from GitHub, or upload [morning-brief.skill](../morning-brief.skill). Both include the required `SKILL.md` and the scheduling resources. The standalone [morning-brief.md](../morning-brief.md) is a readable reference, not the import package.

Each employee gets a **daily 9:00 a.m. Malaysia-time** briefing of live tasks, grouped by overdue, due today, upcoming, no deadline and awaiting review. It includes the existing dashboard task IDs and suggests what to start. The reminder itself does not change tasks. Use `--time 09:30` if that is the preferred start time.

## Activate in each employee's G-Work

1. Load the current SSM/CTC skills from this repository. Keep that employee's Neon connection pinned to their own restricted database login.
2. Ask G-Work to run `SELECT * FROM public.cosec_gwork_identity();` and confirm the returned employee is the signed-in staff member. Stop if unlinked or mismatched. Creating a schedule does not provision staff database access.
3. In that G-Work cowork session, run `python3 gwork/install-morning-briefing.py --staff-id <verified-ID> --staff-name '<verified-name>'` from this repository. The installer uses G-Work's built-in local scheduling API and reads back its result. Running it again updates that employee's existing reminder instead of making a duplicate. It stores no database password.
4. In G-Work **Scheduled Tasks**, select **Run now** once. Verify the staff identity, pending task IDs and dates against the dashboard. Address required permissions for the specific read tool if prompted. Keep the device timezone at Asia/Kuala_Lumpur and G-Work running at the scheduled time.

No reminder has been activated merely by downloading this repository. Without a G-Work session the installer stops without creating a task. The configured result appears in G-Work; no external notification channel is enabled.

## Shared task identity

`task_id` is the existing dashboard task's ID, not the G-Work conversation ID, recurring-reminder ID, skill `run_id` or Excel `job_id`. Starting an existing task updates it to **In progress**. Completing preparation submits that same task for review. Its company, deadline and assignee are retained. CTC uses the dashboard's **Certified true copies** service type. Fees, invoices and approval remain separate actions.

The database setup is maintained in [cosec-desk](https://github.com/joshuachai-code/cosec-desk/blob/main/scripts/migrations/gwork-task-sync.sql). Only provisioned staff connections can read or update permitted records; granting access to the reminder does not grant more database permissions.

Official scheduling reference: [G-Work Scheduled Tasks](https://www.gptbots.ai/docs/workspace/app-settings/scheduled-tasks).
