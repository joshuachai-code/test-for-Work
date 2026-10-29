# Boardroom CTC workflow

Download [ctc-billing.skill](ctc-billing.skill) for the packaged workflow, or inspect [the skill source](ctc-billing/SKILL.md).

The skill covers company lookup from locally synced OneDrive, scanned-copy quantity review, recording work in both Excel books, approval, and Finance handoff. The [local executive dashboard](dashboard/README.md) reads the two record books and exposes aggregate reporting.

This checkout is configured for the original Mac workspace. Before using another computer, update `ctc-billing/scripts/books.json` with its OneDrive location and resolve the Node/Python runtimes and `@oai/artifact-tool` dependencies. Dependency symlinks, access keys, client information, and live workbooks are not included.

To create fresh blank workbook templates, run `dashboard/setup/create-books.mjs` with the bundled Node runtime after linking its `node_modules` to the bundled package directory. It creates templates in `outputs/ctc-books`; copy them to the configured OneDrive CTC Records folder only if new books are needed. Do not overwrite working books.

Run `python3 dashboard/server.py` to start the dashboard on `http://127.0.0.1:8765`. It prints the path to the local access-key file. The prototype uses a shared key and does not verify individual executive identities or cloud sync completion.
