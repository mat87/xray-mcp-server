import os
import json
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("xray_mcp_server")

XRAY_AUTH_URL = "https://xray.cloud.getxray.app/api/v1/authenticate"
XRAY_GRAPHQL_URL = "https://xray.cloud.getxray.app/api/v2/graphql"


async def get_xray_token() -> str:
    client_id = os.environ.get("XRAY_CLIENT_ID")
    client_secret = os.environ.get("XRAY_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise ValueError("Lack of environment variables: XRAY_CLIENT_ID and/or XRAY_CLIENT_SECRET.")

    async with httpx.AsyncClient() as client:
        response = await client.post(XRAY_AUTH_URL, json={"client_id": client_id, "client_secret": client_secret})
        response.raise_for_status()
        return response.text.strip('"')


def read_steps_from_json(file_path: str) -> list[dict]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File does not exist: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        steps = json.load(f)

    if not isinstance(steps, list):
        raise ValueError("JSON file must contain a list (array) of steps.")

    return steps


async def get_issue_internal_id(issue_key: str, token: str) -> str:
    """Fetches the internal Xray issue ID based on the Jira issue key (e.g., VCAGTEST-12345)"""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    query = """
    query getTestId($jql: String!) {
        getTests(jql: $jql, limit: 1) {
            results {
                issueId
            }
        }
    }
    """
    payload = {"query": query, "variables": {"jql": f"key = '{issue_key}'"}}

    async with httpx.AsyncClient() as client:
        response = await client.post(XRAY_GRAPHQL_URL, headers=headers, json=payload, timeout=10.0)
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            raise ValueError(f"GraphQL error fetching issue ID: {data['errors']}")

        results = data.get("data", {}).get("getTests", {}).get("results", [])
        if not results:
            raise ValueError(f"Issue {issue_key} not found or is not recognized as a Test issue by Xray.")

        return results[0]["issueId"]


async def add_steps_via_graphql(issue_id: str, steps: list[dict], token: str) -> int:
    """Injects test steps one by one using a GraphQL mutation."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    mutation = """
    mutation addStep($issueId: String!, $action: String, $data: String, $result: String) {
        addTestStep(
            issueId: $issueId,
            step: {
                action: $action,
                data: $data,
                result: $result
            }
        ) {
            id
        }
    }
    """

    added_count = 0
    async with httpx.AsyncClient() as client:
        for step in steps:
            # Get values and strip whitespace
            action_str = step.get("action", "").strip()
            data_str = step.get("data", "").strip()
            result_str = step.get("result", "").strip()

            # Xray GraphQL prefers `null` (None) instead of empty strings for optional fields
            variables = {
                "issueId": issue_id,
                "action": action_str if action_str else "Missing action",
                "data": data_str if data_str else None,
                "result": result_str if result_str else None
            }

            response = await client.post(XRAY_GRAPHQL_URL, headers=headers,
                                         json={"query": mutation, "variables": variables}, timeout=15.0)
            response.raise_for_status()
            resp_data = response.json()

            if "errors" in resp_data:
                raise ValueError(f"Failed to add step '{action_str[:30]}...': {json.dumps(resp_data['errors'])}")

            added_count += 1

    return added_count


@mcp.tool()
async def import_test_from_file(issue_key: str, file_path: str) -> str:
    """
    Loads test steps from a local JSON file and imports them into an existing Xray test issue using GraphQL.
    """
    try:
        # 1. Read file and authenticate
        steps = read_steps_from_json(file_path)
        token = await get_xray_token()

        # 2. Map Jira key to GraphQL ID
        issue_id = await get_issue_internal_id(issue_key, token)

        # 3. Synchronously add steps
        added_count = await add_steps_via_graphql(issue_id, steps, token)

        return f"SUCCESS! Successfully imported {added_count} steps to the issue {issue_key}."

    except Exception as e:
        return f"ERROR: An error occurred during the import: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport='stdio')