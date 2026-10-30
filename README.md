# Boardroom workflows

## CTC billing

Download [ctc-billing.skill](ctc-billing.skill) for the packaged workflow, or inspect [the skill source](ctc-billing/SKILL.md).

The skill covers company lookup from locally synced OneDrive, scanned-copy quantity review, recording work in both Excel books, approval, and Finance handoff. The [local executive dashboard](dashboard/README.md) reads the two record books and exposes aggregate reporting.

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
6. Save matching, verified copies to both OneDrive and local storage, and return links to both.

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

SSM form completion does not update the CTC record books or add SSM activity to the dashboard. Company records and completed forms are not included in this repository.
