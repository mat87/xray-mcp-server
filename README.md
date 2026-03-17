# Xray MCP Server 🚀

This project is a **Model Context Protocol (MCP)** server written in Python that allows AI assistants (e.g., Gemini CLI, Claude Desktop) to directly integrate with your **Jira Xray Cloud** instance.

With this tool, you can use natural language to ask your AI model to load a local JSON file containing test steps and append them to an existing test issue in Xray (via the `/bulk` endpoint).

## 🌟 Features
* **Automatic Authentication:** The server automatically fetches and manages the Bearer token using your Xray API credentials.
* **Local File Import:** Reads local JSON files containing predefined Test Steps.
* **Seamless AI Integration:** Exposes the `import_xray_test_from_file` tool, which AI models can natively understand and execute.

---

## 📋 Prerequisites
* **Python 3.10** or higher installed.
* API Keys generated in Jira Xray Cloud (`Client ID` and `Client Secret`).
* An MCP-compatible client (e.g., Gemini CLI or Claude Desktop).

---

## 🛠️ Installation

**1. Clone the repository:**
```bash
git clone https://github.com/mat87/xray-mcp-server.git
cd xray-mcp-server
```

**2. (Optional) Create a virtual environment:**
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
        "/ABSOLUTE/PATH/TO/xray-mcp-server/xray_mcp_server.py"
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

Once the server is connected, simply type a natural language request to your AI assistant in the chat:

> *"Load the test steps from C:/my_tests/login.json and add them to the PROJ-123 test issue."*

> *"Update the steps in the PROJ-99 Xray issue using the file /Users/mac/tests/cart.json"*

The model will automatically extract the issue key and the file path, and execute the script in the background.

---

## 📄 Required JSON File Format
Your local JSON file (e.g., `login.json`) must contain an array of test steps. It should **not** include the issue key (the server handles that automatically). Example:

```json
[
  {
    "action": "Open the home page",
    "data": "url: example.com",
    "result": "The page loads successfully"
  },
  {
    "action": "Enter username and password",
    "data": "login: testuser, pass: 12345",
    "result": "The user is logged in"
  }
]
```