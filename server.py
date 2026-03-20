import os
import json
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("xray_mcp_server")

XRAY_AUTH_URL = "https://xray.cloud.getxray.app/api/v1/authenticate"
XRAY_GRAPHQL_URL = "https://xray.cloud.getxray.app/api/v2/graphql"


def _get_step_value(step: dict, keys: list[str], default_value: str = "") -> str:
    """
    Helper to extract a value from a step dictionary, trying multiple keys.
    Returns the first non-empty string value found, or the default_value.
    """
    for key in keys:
        value = step.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default_value


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
                action_str = _get_step_value(step, ["action", "step", "description"], "Missing action")
                data_str = _get_step_value(step, ["data", "input"])
                result_str = _get_step_value(step, ["result", "expected_result"])

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

    except (ValueError, httpx.HTTPStatusError) as e:
        return f"ERROR: Xray API interaction failed: {str(e)}"
    except Exception as e:
        return f"ERROR: An unexpected error occurred in add_steps_to_existing_xray_test: {type(e).__name__} - {str(e)}"


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
            action_str = _get_step_value(step, ["action", "step", "description"], "Missing action")
            data_str = _get_step_value(step, ["data", "input"])
            result_str = _get_step_value(step, ["result", "expected_result"])

            action_escaped = json.dumps(action_str)
            data_escaped = json.dumps(data_str) if data_str else "null"
            result_escaped = json.dumps(result_str) if result_str else "null"

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

    except (ValueError, httpx.HTTPStatusError) as e:
        return f"ERROR: Xray API interaction failed: {str(e)}"
    except Exception as e:
        return f"ERROR: An unexpected error occurred in create_new_xray_test: {type(e).__name__} - {str(e)}"


# ==========================================
# TOOL 3: Copy Attachments between Jira Issues
# ==========================================
@mcp.tool()
async def copy_jira_attachments(source_issue_key: str, target_issue_key: str) -> str:
    """
    Downloads all attachments (like UI designs/images) from a source Jira issue and uploads them to a target Jira issue.
    Call this right after creating a new test, to ensure image tags like !image.png! work correctly.
    """
    jira_domain = os.environ.get("JIRA_DOMAIN")
    jira_email = os.environ.get("JIRA_EMAIL")
    jira_api_token = os.environ.get("JIRA_API_TOKEN")

    if not all([jira_domain, jira_email, jira_api_token]):
        return "ERROR: Missing Jira credentials. Please set JIRA_DOMAIN, JIRA_EMAIL, and JIRA_API_TOKEN in the environment variables."

    auth = httpx.BasicAuth(jira_email, jira_api_token)
    base_url = f"https://{jira_domain}/rest/api/3"

    try:
        async with httpx.AsyncClient(auth=auth, follow_redirects=True) as client:
            # 1. Fetch attachment metadata from the source issue
            resp = await client.get(f"{base_url}/issue/{source_issue_key}?fields=attachment", timeout=15.0)
            resp.raise_for_status()
            attachments = resp.json().get("fields", {}).get("attachment", [])

            if not attachments:
                return f"No attachments found in {source_issue_key}."

            copied_files = []

            # 2. Download each attachment and upload to the target issue
            for att in attachments:
                att_name = att["filename"]
                content_url = att["content"]

                # Download from source
                dl_resp = await client.get(content_url, timeout=30.0)
                dl_resp.raise_for_status()

                # Upload to target
                # Jira requires this specific header for attachments
                headers = {"X-Atlassian-Token": "no-check"}
                files = {'file': (att_name, dl_resp.content)}

                up_resp = await client.post(
                    f"{base_url}/issue/{target_issue_key}/attachments",
                    headers=headers,
                    files=files,
                    timeout=30.0
                )
                up_resp.raise_for_status()
                copied_files.append(att_name)

        return f"SUCCESS: Copied {len(copied_files)} attachments ({', '.join(copied_files)}) to {target_issue_key}."

    except (ValueError, httpx.HTTPStatusError) as e:
        return f"ERROR: Jira API interaction failed: {str(e)}"
    except Exception as e:
        return f"ERROR: An unexpected error occurred in copy_jira_attachments: {type(e).__name__} - {str(e)}"

if __name__ == "__main__":
    mcp.run(transport='stdio')
