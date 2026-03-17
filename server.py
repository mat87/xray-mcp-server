import os
import json
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("xray_mcp_server")

XRAY_AUTH_URL = "https://xray.cloud.getxray.app/api/v1/authenticate"
XRAY_BULK_IMPORT_URL = "https://xray.cloud.getxray.app/api/v1/import/test/bulk"


async def get_xray_token() -> str:
    client_id = os.environ.get("XRAY_CLIENT_ID")
    client_secret = os.environ.get("XRAY_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise ValueError(
            "Lack of environment variables: XRAY_CLIENT_ID and/or XRAY_CLIENT_SECRET.")

    async with httpx.AsyncClient() as client:
        response = await client.post(XRAY_AUTH_URL, json={"client_id": client_id, "client_secret": client_secret})
        response.raise_for_status()
        return response.text.strip('"')


def read_steps_from_json(file_path: str) -> list[dict]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File does not exists: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        steps = json.load(f)

    if not isinstance(steps, list):
        raise ValueError("JSON file must contain a list (array) of steps, not a single object.")

    return steps


async def send_bulk_import_request(issue_key: str, steps: list[dict], token: str) -> httpx.Response:
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

    async with httpx.AsyncClient() as client:
        response = await client.post(XRAY_BULK_IMPORT_URL, headers=headers, json=payload, timeout=30.0)
        response.raise_for_status()
        return response


@mcp.tool()
async def import_xray_test_from_file(issue_key: str, file_path: str) -> str:
    """
    Loads test steps from a local JSON file and imports them into an existing Xray test issue.

    Args:
        issue_key: The Jira issue key where the steps will be imported, e.g., "PROJ-123".
        file_path: The absolute path to the local JSON file containing the steps, e.g., "C:/tests/steps.json".
    """
    try:
        steps = read_steps_from_json(file_path)
        token = await get_xray_token()
        response = await send_bulk_import_request(issue_key, steps, token)

        return f"Success! File '{file_path}' loaded and steps successfully imported into test {issue_key}. (Status: {response.status_code})"

    except FileNotFoundError as e:
        return f"Read error: {str(e)}"
    except json.JSONDecodeError:
        return f"Parsing error: The specified file '{file_path}' is not a valid JSON file."
    except ValueError as e:
        return f"Validation error: {str(e)}"
    except httpx.HTTPStatusError as http_err:
        return f"Xray API error (HTTP {http_err.response.status_code}): {http_err.response.text}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport='stdio')
