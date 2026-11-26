---
name: ctc-billing
description: Prepare certified true copy work in G-Work, confirm page and copy counts, save the review file and both OneDrive record books, and submit the assigned Cosec Desk task for Team Leader review.
---

# CTC preparation

Use the selected Cosec Desk assignment, company and assignee. Check the exact task ID and current status through the worker’s scoped connection. Keep task, job and run IDs distinct. A scan preview is read-only. Reuse an existing attachment and confirmed counts when continuing a preview. Check previously submitted or verified work before attempting any write.

Inspect the attached batch, grouping by document and excluding covers and duplicate scans. If only extracted text is available, use `python3 scripts/preview.py "/path/to/batch.pdf"`. A matching reviewed hash provides evidence for those bytes. For an unfamiliar batch, inspect the rendered pages. Resolve only actual gaps.

Ask the Team Member in one message: **“How many certified pages are in one copy, and how many copies did you complete?”** Prefill supported counts and ask only for missing information or confirmation. A request for five sets is distinct from five completed sets. Calculate total certified pages as pages per copy × completed copies, exactly once. Carry actual printed-page evidence separately. A routing page may be printed without being certified. If printing is unknown, leave it unknown for the Director to reconcile. Never prompt staff for prices, retrieve rate cards, calculate monetary amounts, or put amounts in chat, the two books, a review file you generate, or task history. Pricing belongs on the Director’s billing page.

Show the task, counts and completed filename. Ask **“Is this work complete and ready to save and submit to your Team Leader?”** Wait for confirmation. If the task or deliverable changes, confirm the new target. An explicit books-only request does not authorize submission. For work without a task ID, match or create the correct assigned task with authorization before publishing its review file.

On confirmation follow [saving and submission](references/live-workflow.md). Save the completed deliverable under `OneDrive/Boardroom/Completed Forms/<task_id>/`, retaining the two books under `Boardroom/CTC Records/`. Reopen and verify the saved file and both rows before submitting the same assignment. Report quantities, review path and status. On the Team Leader side retrieve that file under the permitted task ID and show it before requesting an approval decision. Leave monetary details to the Director after verification.
