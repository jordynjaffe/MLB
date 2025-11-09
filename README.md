 Terraform Run Management Automation

This project automates the management of Terraform Cloud (TFC) runs within an organization, including discarding redundant runs, triggering new runs, and optionally applying safe changes. It was originally developed as part of my internship work to streamline infrastructure workflows.

Note:
This public version has been sanitized — all internal URLs, organization names, and environment variable conventions related to Major League Baseball (MLB) have been omitted or replaced with generic placeholders. The shared code reflects my implementation logic, error handling, and automation design, not any proprietary MLB infrastructure details.

Key Features

- Fetches and manages Terraform workspace runs via the Terraform Cloud REST API
- Automatically discards pending or planning runs to maintain clean pipeline states
- Triggers new infrastructure runs when workspaces are idle
- Logs runs that require manual review (for example, destructive or complex plans)
- Supports optional auto-apply for non-destructive (“add-only”) plans
- Includes built-in polling, rate limiting, and error handling

Technologies Used

Python 3.10+

Terraform Cloud / Terraform Enterprise API

Requests (for API interactions)

Argparse (for command-line configuration)

CSV logging (for review and auditing)

Example Use Case

The script can be configured to:

Identify all workspaces matching a naming pattern.

Discard any in-progress runs that block automation.

Trigger a new plan and either:

Automatically apply it if it only contains additions, or

Log it for manual review if it includes modifications or deletions.

Environment Setup

Set an environment variable for your Terraform API token:

export API_TOKEN="your_terraform_cloud_token"


Then run the script:

python3 manage_runs.py --name_regex "example-workspace" --apply

Example Output
Processing workspace: ws-12345
Discarding run run-98765 with status planning
New run ID: run-12345
Current run status: planned_and_finished
Plan result: +2 ~0 -0
Only additions found. Auto-applying...
Successfully auto-applied.

Ethical Disclosure

This code is derived from personal work written during my time at Major League Baseball (MLB) but has been fully scrubbed of all proprietary, identifying, or sensitive details.
All domain names, tokens, organization identifiers, and process-specific labels have been anonymized to ensure compliance with professional and ethical standards.