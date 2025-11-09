import os
import requests
import time
import csv
import json
import re
import argparse


# Use a generic API token environment variable name
API_TOKEN = os.environ["API_TOKEN"]

# Generic Terraform Enterprise base URLs (redacted from internal use)
TFC_BASE = "https://terraform.example.net/api/v2"
TFC_UI_BASE = "https://terraform.example.net/app"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/vnd.api+json"
}


def get_runs(workspace_id):
    """Fetch all runs for a given Terraform workspace."""
    url = f"{TFC_BASE}/workspaces/{workspace_id}/runs"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()["data"]


def discard_run(run_id):
    """Discard a pending or planning run."""
    url = f"{TFC_BASE}/runs/{run_id}/actions/discard"
    resp = requests.post(url, headers=headers, json={"comment": "Discarded by automation"})
    if resp.status_code == 200:
        print(f"Discarded run {run_id}")
    else:
        print(f"Failed to discard run {run_id}: {resp.text}")


def log_review_link(workspace_id, run_id, adds, changes, destroys):
    """Log runs that require manual review to a CSV file."""
    run_url = f"{TFC_UI_BASE}/{workspace_id}/runs/{run_id}"
    summary = f"+{adds} ~{changes} -{destroys}"
    with open("review_links.csv", "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([workspace_id, run_id, run_url, summary])
    print(f"Logged for manual review: {run_url}")


def get_workspace_ids(organization, name_regex=None, tag=None):
    """Retrieve workspace IDs for a given organization, filtered by regex or tag."""
    url = f"{TFC_BASE}/organizations/{organization}/workspaces"
    workspace_ids = []
    page = 1
    while True:
        resp = requests.get(url + f"?page[number]={page}", headers=headers)
        if resp.status_code != 200:
            print(f"Failed to fetch workspaces: {resp.text}")
            break
        data = resp.json()["data"]
        if not data:
            break
        for ws in data:
            ws_name = ws["attributes"]["name"]
            ws_tags = ws["attributes"].get("tags", [])
            if name_regex and not re.search(name_regex, ws_name):
                continue
            if tag and tag not in ws_tags:
                continue
            workspace_ids.append(ws["id"])
        page += 1
    return workspace_ids


def trigger_run(workspace_id, do_apply=False):
    """Trigger a new Terraform run and optionally auto-apply if only additions are found."""
    url = f"{TFC_BASE}/runs"
    payload = {
        "data": {
            "attributes": {
                "is-destroy": False,
                "message": "Triggered by automation after discarding runs"
            },
            "type": "runs",
            "relationships": {
                "workspace": {
                    "data": {
                        "type": "workspaces",
                        "id": workspace_id
                    }
                }
            }
        }
    }

    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 201:
        print(f"Failed to trigger a new run: {resp.text}")
        return

    run_id = resp.json()["data"]["id"]
    print(f"New run ID: {run_id}")
    run_url = f"{TFC_BASE}/runs/{run_id}"

    for _ in range(30):
        run_resp = requests.get(run_url, headers=headers)
        status = run_resp.json()["data"]["attributes"]["status"]
        print(f"Current run status: {status}")

        if status in ["planned", "planned_and_finished"]:
            print("Reached 'planned_and_finished'. Checking for plan data...")
            plan_data = run_resp.json()["data"]["relationships"].get("plan", {}).get("data")
            if not plan_data:
                print("Plan ID not found. Skipping apply.")
                return

            plan_id = plan_data["id"]
            plan_url = f"{TFC_BASE}/plans/{plan_id}"

            adds = changes = destroys = -1
            for i in range(10):
                plan_resp = requests.get(plan_url, headers=headers)
                if plan_resp.status_code == 200:
                    plan_json = plan_resp.json()
                    attrs = plan_json.get("data", {}).get("attributes", {})
                    if "resource-additions" in attrs:
                        adds = attrs.get("resource-additions", 0)
                        changes = attrs.get("resource-changes", 0)
                        destroys = attrs.get("resource-destructions", 0)
                        print(f"Plan result: +{adds} ~{changes} -{destroys}")
                        break
                else:
                    print(f"Plan not ready: {plan_resp.status_code}")
                time.sleep(6)

            if adds == -1:
                print("Timed out waiting for plan resource counts.")
                return

            if adds == 0 and changes == 0 and destroys == 0:
                print("No changes to apply. Done.")
                return
            elif changes > 0 or destroys > 0:
                print("Plan includes modifications or deletions. Logging for manual review.")
                log_review_link(workspace_id, run_id, adds, changes, destroys)
                return
            elif adds > 0:
                if do_apply:
                    print("Only additions found. Auto-applying...")
                    apply_url = f"{TFC_BASE}/runs/{run_id}/actions/apply"
                    apply_resp = requests.post(apply_url, headers=headers, json={"comment": "Auto-applied by script"})
                    if apply_resp.status_code == 200:
                        print("Successfully auto-applied.")
                    else:
                        print(f"Failed to apply: {apply_resp.text}")
                else:
                    print("Apply step is skipped (use --apply to enable).")
                return

        elif status in ["errored", "canceled", "applied"]:
            print(f"Run ended with status: {status}. Exiting.")
            return

        time.sleep(6)

    print("Timed out waiting for run to become 'planned_and_finished'.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Auto-apply runs with only additions")
    parser.add_argument("--name_regex", type=str, default="example-workspace", help="Regex to filter workspace names")
    args = parser.parse_args()

    # Clear CSV at start of each execution
    with open("review_links.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["workspace_id", "run_id", "run_url", "summary"])

    ORGANIZATION = "example_org"
    workspace_ids = get_workspace_ids(ORGANIZATION, name_regex=args.name_regex)

    for ws_id in workspace_ids:
        print(f"Processing workspace: {ws_id}")
        runs = get_runs(ws_id)
        any_active = False
        for run in runs:
            run_id = run["id"]
            status = run["attributes"]["status"]

            if status in ["pending", "planned", "planning", "cost_estimating"]:
                print(f"Discarding run {run_id} with status {status}")
                discard_run(run_id)
            elif status == "applying":
                print(f"Run {run_id} is applying. Skipping.")
                any_active = True
            else:
                print(f"Run {run_id} status is {status}. Skipping discard.")

        time.sleep(5)

        runs = get_runs(ws_id)
        for run in runs:
            status = run["attributes"]["status"]
            if status in ["pending", "planned", "planning", "cost_estimating", "applying"]:
                print(f"Run {run['id']} still active. Not triggering.")
                break
        else:
            print("No active runs. Triggering new one.")
            trigger_run(ws_id, do_apply=args.apply)


if __name__ == "__main__":
    main()
