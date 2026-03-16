import os
import json
import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("xray_mcp_server")

XRAY_AUTH_URL = "https://xray.cloud.getxray.app/api/v1/authenticate"
XRAY_BULK_IMPORT_URL = "https://xray.cloud.getxray.app/api/v1/import/test/bulk"


def get_xray_token() -> str:
    client_id = os.environ.get("XRAY_CLIENT_ID")
    client_secret = os.environ.get("XRAY_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise ValueError(
            "Lack of environment variables: XRAY_CLIENT_ID and/or XRAY_CLIENT_SECRET.")

    response = requests.post(XRAY_AUTH_URL, json={"client_id": client_id, "client_secret": client_secret})
    response.raise_for_status()

    return response.text.strip('"')


@mcp.tool()
def import_xray_test_from_file(issue_key: str, file_path: str) -> str:
    """
    Loads steps from a local JSON file and imports them into an existing test in Xray.

    Args:

    issue_key: The key of the Jira issue into which the steps are being imported, e.g., "PROJ-123"

    file_path: The full path to the JSON file on disk, e.g., "C:/my_tests/steps.json"

    """
    try:
        if not os.path.exists(file_path):
            return f"Error: no file found: {file_path}"

        with open(file_path, 'r', encoding='utf-8') as f:
            steps = json.load(f)

        if not isinstance(steps, list):
            return "Error: JSON file must contain a list of steps [ { 'action': '...', ... } ]."

        token = get_xray_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        payload = [
            {
                "testIssueKey": issue_key,
                "steps": steps
            }
        ]

        response = requests.post(XRAY_BULK_IMPORT_URL, headers=headers, json=payload)
        response.raise_for_status()

        return f"Success! File '{file_path}' loaded and steps successfully imported into test {issue_key}. (Status: {response.status_code})"

    except json.JSONDecodeError:
        return f"Parsing error: The specified file '{file_path}' is not a valid JSON file."
    except requests.exceptions.HTTPError as http_err:
        error_details = response.text if 'response' in locals() else "No details"
        return f"HTTP Xray Error: {http_err} - Details: {error_details}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport='stdio')
