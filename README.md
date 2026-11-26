# Boardroom workflows

## Daily tasks in G-Work

For G-Work GitHub import, use the [morning-brief skill folder](morning-brief/) with its [SKILL.md](morning-brief/SKILL.md). For file upload, download [morning-brief.skill](morning-brief.skill). The package contains `SKILL.md` at its archive root, the scheduling script and the prompt; it does not require the rest of this repository. [morning-brief.md](morning-brief.md) remains a readable reference, not the import package.

The [morning briefing setup](gwork/README.md) checks each linked employee's live dashboard tasks and deadlines at **9:00 a.m. Malaysia time** (9:30 optional). It lists overdue, due today, upcoming and review work with the exact dashboard `task_id`. Activate it inside that employee's G-Work session; downloading this repository does not enable a schedule.

When the employee chooses an existing task, both skills start and submit **that same task ID**, preserving its deadline and assignee. CTC maps to the dashboard's existing **Certified true copies** task type. The morning briefing itself is read-only.

## Shared production dashboard

Both skills now include a final step to record completed preparation in the live Neon database used by [Cosec Desk](https://cosec-desk.vercel.app). They use the connected staff member's restricted database identity, check current dashboard permissions, submit the preparation task for review, and read it back before reporting success. Retrying the same run does not create a duplicate task.

G-Work must load the updated skill and use a connection that permits writes while remaining pinned to that staff member's restricted database role. Updating this repository alone does not update an already imported G-Work copy or change its connection settings. Missing access or a read-only connection is reported as a pending dashboard update, never as a successful save.

See the [SSM database-save instructions](ssm-form-filling/references/dashboard-completion.md) or [CTC database-save instructions](ctc-billing/references/dashboard-completion.md). The database implementation and tests are maintained in the application repository: [completion migration](https://github.com/joshuachai-code/cosec-desk/blob/main/scripts/migrations/gwork-skill-completion.sql), [task identity and type migration](https://github.com/joshuachai-code/cosec-desk/blob/main/scripts/migrations/gwork-task-sync.sql), and [permission/retry tests](https://github.com/joshuachai-code/cosec-desk/blob/main/tests/gwork-task-sync.sql).

Task submission does not perform SSM lodgement, approve work, issue invoices, upload output files to Neon, or import Excel financial totals. Staff and Team Leaders see permitted submitted tasks; Director reports follow the dashboard's existing review rules.

## CTC billing

In G-Work, import the [CTC skill folder](ctc-billing/) or upload [ctc-billing.skill](ctc-billing.skill). Re-import after updating an existing installation.

Attach the CTC batch and say **Run CTC billing for this company.** G-Work confirms certified pages per copy and completed copies. After completion confirmation it saves the deliverable in Boardroom/Completed Forms/<task_id>/, records nonfinancial counts in both CTC books and submits the same task for review. The Director configures billing rates in Cosec Desk. An explicit preview is read-only.

Cedar Logistics, Amber Energy, Rimbun Quay Packaging and Saujana Loom Textiles have reviewed scan evidence for the listed exact file hashes. Other files can be rendered for inspection. See [CTC billing](ctc-billing/SKILL.md) for the short run and [the operational workflow](ctc-billing/references/live-workflow.md) for dashboard-linked work.

The skill covers company lookup from locally synced OneDrive, scanned-copy quantity review, recording work in both Excel books, approval, and Finance handoff. Once preparation and both book writes are verified, it records the preparation task in production Cosec Desk. The separate [local executive dashboard](dashboard/README.md) reads the two record books and exposes aggregate reporting.

This checkout is configured for the original Mac workspace. Before using another computer, update `ctc-billing/scripts/books.json` with its OneDrive location and resolve the Node/Python runtimes and `@oai/artifact-tool` dependencies. Dependency symlinks, access keys, client information, and live workbooks are not included.

To create fresh blank workbook templates, run `dashboard/setup/create-books.mjs` with the bundled Node runtime after linking its `node_modules` to the bundled package directory. It creates templates in `outputs/ctc-books`; copy them to the configured OneDrive CTC Records folder only if new books are needed. Do not overwrite working books.

Run `python3 dashboard/server.py` to start the dashboard on `http://127.0.0.1:8765`. It prints the path to the local access-key file. The prototype uses a shared key and does not verify individual executive identities or cloud sync completion.

## SSM form filling

Download [ssm-form-filling.skill](ssm-form-filling.skill) for the reusable document-filling workflow, or use [the SSM skill folder](ssm-form-filling/) for GitHub skill import. Its entry point is [ssm-form-filling/SKILL.md](ssm-form-filling/SKILL.md). It uses each supplied form's fields and layout rather than a fixed SSM template, and supports PDF, scanned forms, Word documents, spreadsheets, and pasted form text.

### Usage

Attach or paste the form and say: “Fill this SSM form for [company name].”

The workflow reuses a form already supplied and requests it only once if absent. It asks for the company name only when needed to identify the relevant records. Company details are read automatically from the locally synced OneDrive `Boardroom/Company Information` folder; workers are not routinely asked to choose a source or retype those details.

1. Inspect the form and identify the applicable sections.
2. Read the relevant company records and check whether they support every required field.
3. Ask only for specific missing, conflicting, unreadable, or updated information.
4. Fill a working copy while preserving the form's layout and wording.
5. Reopen the saved output and compare every populated field against its source or documented calculation. Check completeness, totals, repeated details, and rendered appearance.
6. Save matching, verified copies to both OneDrive and local storage.
7. Record the finished preparation through the staff-scoped Neon save function and read back the saved task.
8. Return links to both files and report the database result separately: saved and checked, pending, or not submitted.

Unsupported values must not be invented. Unresolved required information keeps the result from being released as verified. Data-complete forms that still need human signatures are labelled `READY-FOR-SIGNATURE`; the workflow does not create signatures or automatically lodge documents with SSM.

### Source and output folders

The package contains `ssm-form-filling/config.json` with these defaults:

| Purpose | Location |
| --- | --- |
| Company records | `/Users/joshua.c/Library/CloudStorage/OneDrive-Personal/Boardroom/Company Information` |
| OneDrive completed forms | `/Users/joshua.c/Library/CloudStorage/OneDrive-Personal/Boardroom/Completed Forms` |
| Local completed forms | `/Users/joshua.c/Documents/ChatGPT/Boardroom/Completed Forms` |

Outputs use company-specific subfolders and unique filenames. On another computer, update the package's configuration to the correct source and output folders before use. The `.skill` file is a ZIP package containing the instructions, configuration, references, and Python delivery helper.

The delivery helper checks the recorded verification manifest and confirms matching file hashes in both destinations. It does not independently fact-check company information; the source and visual verification steps remain necessary. A successful save into the synced OneDrive folder does not itself confirm cloud upload.

SSM form completion does not update the CTC record books or the local Excel report. A successful, checked database save adds a preparation task to production Cosec Desk under its existing staff permissions and review rules. Company records and completed forms are not included in this repository.
