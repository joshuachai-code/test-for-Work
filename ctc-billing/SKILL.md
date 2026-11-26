---
name: ctc-billing
description: Count certified pages, collect job-specific CTC and printing costs, then record a CTC billing run in both OneDrive Excel books. Also supports an explicit read-only preview and the Boardroom operational workflow.
---

# CTC billing

## Identify the requested outcome

A request to **run CTC billing**, including a demo run, includes the two configured OneDrive record books. An explicit **preview only**, estimate, scan review or dry run stays read-only. A known demo scan selects the short inspection path below, but never changes a request to record into a preview. “Save it” after a preview continues the same job and attachment. Preserve its copy request, job ID, run ID and confirmed inputs across turns.

For real operational work or a selected live dashboard task, follow [the live workflow](references/live-workflow.md) for its stages, task identity and submission checks. A standalone request to record a demo in the Excel books needs only the steps below. Use [dashboard actions](references/dashboard-actions.md) for explicit dashboard operations.

## Inspect the supplied pages

Use the attachment already present. If its pages are visible, inspect those directly. If the file tool shows only extracted text, use the bundled helper once with the existing PDF path before asking for images:

```sh
python3 scripts/preview.py "/path/to/attached-batch.pdf"
```

For a PDF matching a previously visually reviewed original, the helper returns page-numbered evidence. This completes visual reconciliation for those bytes. Report the confirmed count and use that result for the books. Never describe the current run as a fresh visual inspection when it reused the prior review. New or modified files can be inspected through the returned page images. Use `--fresh` only for an explicit fresh inspection. Request only genuinely unresolved pages. For a read-only estimate with clear page-delimited text, state its text-based basis and give the estimate. Do not require six image uploads just to provide an estimate.

Group evidence by company and document. Count distinct certified pages, exclude cover sheets, and resolve duplicates against the routing note or other evidence of physical copy quantity. Quote the included pages and any exclusions in one short breakdown. Match the company name and ID when a profile is available. A volume of text, an unrelated profile, or a filename alone is insufficient evidence.

## Ask for the two costs for this job

After the count, ask in **one message**: “What CTC rate in RM per certified page should I use, and what is the total printing cost in RM for this job? Enter RM0 if printing is free.” If the worker personally gave one value for this job, ask only for the missing one. If printing is quoted per printed page, obtain the printed-page quantity and multiply. Never assume every certified page was printed. Use only explicit job-specific user input. Prior jobs, memory, PDFs, company profiles, stored defaults and model-suggested figures cannot confirm either price. Wait for the reply with the count already established. No amount is agreed until both answers are known.

Calculate CTC subtotal = certified pages × CTC rate per page. Add the total printing charge exactly once. An explicit estimate-only request ends with the breakdown and estimate.

## Save a run to both OneDrive books

For a billing run, the worker's pricing reply continues the existing authorisation to save. Keep the same job and run IDs and avoid another approval question. Use the printed copy request as the job ID if no earlier assignment ID exists. If starting its first identified run, use that job ID with the suffix `-01` as the run ID. Reuse an existing key on retry; preserve reviewed or issued records. Keep known task IDs separate.

Prepare the job JSON with the fields listed under **Write both Excel books** in [the live workflow](references/live-workflow.md). Include company, work date, separate agent attribution, verified quantity and evidence, billing unit `page`, both user-confirmed costs (`rate_rm` and total `printing_rm`), and the unbilled total in integer sen. Use `billing_status: pending` until subsequent billing action is established. Record and verify the two rows with the installed helper:

```sh
python3 scripts/records.py record-confirmed "/path/to/this-job.json"
```

Report each workbook and the job reference only after both saved rows have been read back. Distinguish successful local saves in the OneDrive folder from cloud sync. If the write fails, report which books were verified, the actual failure and any outstanding action. Never report a preview, a staged file or a dashboard entry as a workbook save. During the short demo path skip memory, task listing, browser setup, tool searches, SQL and dashboard operations.
