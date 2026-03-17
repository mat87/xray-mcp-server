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


async def get_issue_internal_id(issue_key: str, token: str) -> str:
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


# ==========================================
# TOOL 1: Add steps to existing Jira issue
# ==========================================
@mcp.tool()
async def add_steps_to_existing_xray_test(issue_key: str, steps: list[dict]) -> str:
    """
    Adds manual UI test steps directly to an existing Xray Test issue.
    Call this tool when the user asks to add test steps to an existing Jira issue.
    """
    try:
        token = await get_xray_token()
        issue_id = await get_issue_internal_id(issue_key, token)

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
                action_raw = step.get("action") or step.get("step") or step.get("description") or "Missing action"
                data_raw = step.get("data") or step.get("input") or ""
                result_raw = step.get("result") or step.get("expected_result") or ""

                action_str = str(action_raw).strip()
                data_str = str(data_raw).strip()
                result_str = str(result_raw).strip()

                variables = {
                    "issueId": issue_id,
                    "action": action_str if action_str else "Missing action (Check inputs)",
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

        return f"SUCCESS! Successfully added {added_count} steps to the issue {issue_key}."

    except Exception as e:
        return f"ERROR: An error occurred: {str(e)}"


# ==========================================
# TOOL 2: Create new xray test with steps
# ==========================================
@mcp.tool()
async def create_new_xray_test(project_key: str, summary: str, steps: list[dict]) -> str:
    """
    Creates a brand new Xray Test issue directly in Jira with the provided manual UI steps.
    Call this tool when the user asks you to invent/generate test steps and create a new test in Jira.
    """
    try:
        token = await get_xray_token()

        steps_graphql = ""
        for step in steps:
            action_raw = step.get("action") or step.get("step") or step.get("description") or "Missing action"
            data_raw = step.get("data") or step.get("input") or ""
            result_raw = step.get("result") or step.get("expected_result") or ""

            action_escaped = json.dumps(str(action_raw).strip())
            data_escaped = json.dumps(str(data_raw).strip()) if str(data_raw).strip() else "null"
            result_escaped = json.dumps(str(result_raw).strip()) if str(result_raw).strip() else "null"

            steps_graphql += f"{{ action: {action_escaped}, data: {data_escaped}, result: {result_escaped} }},\n"

        summary_escaped = json.dumps(summary)
        project_key_escaped = json.dumps(project_key)

        mutation = f"""
        mutation {{
            createTest(
                testType: {{ name: "Manual" }},
                steps: [
                    {steps_graphql}
                ],
                jira: {{
                    fields: {{
                        summary: {summary_escaped},
                        project: {{ key: {project_key_escaped} }}
                    }}
                }}
            ) {{
                test {{
                    jira(fields: ["key"])
                }}
                warnings
            }}
        }}
        """

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            response = await client.post(XRAY_GRAPHQL_URL, headers=headers, json={"query": mutation}, timeout=20.0)
            response.raise_for_status()
            resp_data = response.json()

            if "errors" in resp_data:
                return f"ERROR: Xray API returned an error: {json.dumps(resp_data['errors'])}"

            created_test = resp_data.get("data", {}).get("createTest", {}).get("test", {})
            jira_data = created_test.get("jira", {})

            issue_key = "UNKNOWN"
            if isinstance(jira_data, dict):
                issue_key = jira_data.get("key", "UNKNOWN")
            elif isinstance(jira_data, str):
                try:
                    issue_key = json.loads(jira_data).get("key", "UNKNOWN")
                except json.JSONDecodeError:
                    pass

            return f"SUCCESS! I've successfully created a new Xray Test issue: {issue_key} with {len(steps)} auto-generated steps."

    except Exception as e:
        return f"ERROR: An unexpected error occurred: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport='stdio')
