# Verification manifest

Create this local JSON after inspecting the exact saved output. Keep it out of the official form. The delivery helper validates the recorded checks and output hash; it does not inspect source documents, infer fields, or perform visual verification for you.

Required keys:

- `output_sha256`: SHA-256 of the exact verified file.
- `status`: `verified` or `ready_for_signature`.
- `inventory_ids`: unique IDs for every field occurrence, including intentionally blank, pre-filled and non-applicable fields in the selected output sections.
- `fields`: one object per inventory ID, with `id`, `outcome`, `reason`, and the additional fields below.
- `unresolved`: an empty array for release. Missing/conflicting required data belongs here and prevents release.
- `visual_review_passed`, `structural_review_passed`, `reconciliation_passed`: booleans set to true only after those checks, or after confirming reconciliation is not relevant and recording why in the run notes.
- `human_actions`: outstanding signature/attestation actions. Must be nonempty when status is `ready_for_signature`; must be empty when status is `verified`.

Field outcomes:

| Outcome | Required evidence |
| --- | --- |
| `matched` | `source_ref` identifying the file/page/cell or explicit worker clarification; `expected` from evidence; `observed` read from the saved output at this field location. Both are nonempty strings and must match exactly. |
| `derived` | Same as matched, plus `calculation` with operands and provenance. `expected` is the verified calculation formatted for this field; `observed` is the saved output value. |
| `not_applicable` | `source_ref` and `reason` establishing the conditional branch; `observed` exactly `""` or `"N/A"` as permitted by the form. |
| `optional_blank` | `reason` explaining why the field is optional; `observed` is `""`. |
| `awaiting_signature` | `reason` identifying the human action; `observed` is `""`; overall status must be `ready_for_signature`. This exception is only for human execution, never a missing company fact. |

`expected` should already reflect a documented, faithful display format, such as date formatting or wrapping. Do not change evidence to match an incorrect output. Do not remove meaningful identifier characters, leading zeros, or differences through broad normalization.

The script checks completeness against your declared inventory. Independently verify that the inventory covers the entire applicable form: a script cannot detect fields you omitted from the inventory. Keep the original evidence references and a concise human-readable run summary so another reviewer can audit each value.
