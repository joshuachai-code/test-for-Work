# Boardroom executive dashboard

Run `python3 dashboard/server.py` from the Boardroom workspace and open http://127.0.0.1:8765. The startup message identifies the executive access-key file. The shared key is for authorised executives; this prototype does not provide individual executive accounts. The server binds to localhost only.

## OneDrive sources

Company master files for the separate company workflow belong in `Company Information` under the configured OneDrive Boardroom root. CTC records are two Excel workbooks in `CTC Records`. Exact paths and headers are configured in `ctc-billing/scripts/books.json`.

The server rereads both workbooks on refresh and shows only aggregates. It checks matching job/run IDs and shared fields, then selects each job's latest matching run by its UTC update timestamp. Conflicting or missing counterparts stop reporting. Staging SQLite data is not added to these totals. OneDrive cloud sync is not verified by a successful local read.

Use `ctc-billing/scripts/records.py record job.json` to update both books. See the CTC skill for the input contract. The helper requires the bundled Python/Node runtimes and artifact-tool dependencies, preserves historical runs, keeps recovery copies in temporary storage, and verifies both local writes. A crash can leave a partial pair; check the reported write state and retry the same job/run after resolving a stale writer lock. Close the workbooks in Excel before updating.

The dashboard reports current pending jobs regardless of reporting period; invoice date controls billed amounts and completion date controls completed jobs. Configurable deadline warnings are 3, 7, 14 or 30 days. Unbilled charges are separate from issued invoice totals. Multi-job invoice allocation and credit notes are not supported by the current CTC writer.

The hosted Boardroom Staff Desk is a design/workflow reference, not a connected data source. Temporary storage holds access credentials, optional staging and recovery files. Clearing it does not delete the OneDrive Excel books.
