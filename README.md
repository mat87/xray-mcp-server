# Xray MCP Server 🚀

This project is a **Model Context Protocol (MCP)** server written in Python that allows AI assistants (e.g., Gemini CLI, Claude Desktop) to directly integrate with your **Jira Xray Cloud** instance.

With this tool, you can use natural language to ask your AI model to generate and directly inject manual test steps into an existing test issue or create brand new test issues in Xray (powered by the synchronous GraphQL API).

## 🌟 Features
* **Automatic Authentication:** The server automatically fetches and manages the Bearer token using your Xray API credentials.
* **Zero-File Workflow:** AI generates test steps in memory and injects them directly into Jira. No intermediate JSON files needed.
* **Synchronous & Reliable:** Bypasses the asynchronous `/bulk` REST API in favor of Xray's GraphQL API (v2), providing instant feedback and eliminating background job timeouts.
* **Seamless AI Integration:** Exposes the `add_steps_to_existing_test` and `create_new_xray_test` tools, which AI models can natively understand and execute.

---

## 📋 Prerequisites
* **Python 3.10** or higher installed.
* API Keys generated in Jira Xray Cloud (`Client ID` and `Client Secret` ask Jira support). 
* An MCP-compatible client (e.g., Gemini CLI or Claude Desktop).

---

## 🛠️ Installation

**1. Clone the repository:**
```bash
git clone https://github.com/mat87/xray-mcp-server.git
cd xray-mcp-server
```

**2. Create a virtual environment:**
It is highly recommended to use a virtual environment to keep dependencies isolated.
```bash
python -m venv venv

# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

**3. Install the required dependencies:**
Make sure you are in the project directory (and your virtual environment is activated, if you created one), then run:
```bash
pip install -r requirements.txt
```

---

## ⚙️ Configuration & Setup

To make this server visible to your AI assistant, you need to add it to your MCP client's configuration file. Remember to provide the **absolute path** to the `server.py`.

### Gemini CLI
Add the server configuration to your Gemini CLI MCP settings file (typically located at `~/.gemini/settings.json`).

```json
{
  "mcpServers": {
    "xray-server": {
      "command": "python",
      "args": [
        "/ABSOLUTE/PATH/TO/xray-mcp-server/server.py"
      ],
      "env": {
        "XRAY_CLIENT_ID": "YOUR_CLIENT_ID_HERE",
        "XRAY_CLIENT_SECRET": "YOUR_CLIENT_SECRET_HERE"
      }
    }
  }
}
```
*After saving the file, restart your Gemini CLI.*

---

## 💡 How to Use (Prompt Examples)

Once the server is connected, simply type a natural language request to your AI assistant in the chat. You don't need to provide any files.

**To add steps to an existing test:**
> *"Generate manual UI test steps for the 'forgot password' flow and inject them directly into the existing Xray Test issue PROJ-123."*

**To create a brand new test from scratch:**
> *"Download the description and requirements from the VCAG-12345 ticket. Analyze them and, based on them, design detailed, manual UI test steps (including actions, test data, and expected results). Then, create a completely new Xray Test ticket in the VCAGTEST project from these steps. The entire report should be in English."*

The model will automatically understand the context, generate the required steps in memory, and execute the GraphQL mutation in the background.