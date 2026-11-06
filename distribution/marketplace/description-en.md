# Excel Reconciliation Assistant

Reconcile Excel and CSV tables by explicit business identifiers and comparison rules. Review field differences, missing records, duplicate identifiers and unresolved items in a filterable workbook with traceable reports.

Use it for order and delivery checks, inventory counts, registration and attendance lists, asset registers, and changes between list versions.

Provide authorized files and scope, establish key and field mappings, run structural preflight, compare records, and receive the workbook, reports and full source-row references. Original files remain read-only and every run creates a new output version.

The deterministic tool preserves text identifiers, isolates duplicate or empty keys, compares decimals precisely, and records explicit tolerance, unit and currency rules. It does not recalculate formulas, infer missing business relationships or perform approvals and account operations.

Requires Python 3.9+ with local file access and execution support. XLSX uses openpyxl>=3.1,<4. CSV comparison and Markdown/JSON delivery can run with the standard library; unavailable formats are reported explicitly. No additional model API key is required.

Standard and WorkBuddy packages are provided. Native WorkBuddy V5.9.3 and Codex CLI execution have been verified on the current Mac. Other documented client directories have installation checks, not native end-to-end compatibility certification.
