# client.py
import json
import requests
import dotenv
import os
from google import genai
import docker
from scraper import universal_scraper

# --- Helper Function to Call API ---
# This is your controller function, slightly modified to construct the URL correctly.
def controller(tool_path: str, argument: str):
    """
    Calls the backend API.
    - tool_path: The first part of the path (e.g., "docker")
    - argument: The rest of the path (e.g., "/pwd/opt/")
    """
    base_url = "http://127.0.0.1:8000/"

    full_url = f"{base_url}{tool_path}{argument}"
    print(f" CLIENT: Making request to: {full_url}")
    try:
        response = requests.get(full_url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌  API Call Failed: {e}")
        return {"status": "error", "message": str(e)}


# --- Load Environment and Initialize Clients ---
dotenv.load_dotenv()
genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

try:
    docker_client = docker.from_env()
    container = docker_client.containers.get("ubuntu_chat12")
    print(f"Container '{container.name}' is running.")
except docker.errors.NotFound:
    print("Container 'ubuntu_chat12' not found. Please start it first.")

tools = """
<tools>
  <tool>
    <name>execute_docker_command</name>
    <description>Execute a command (like ls, pwd, cat) inside the running Docker container at a specified path.</description>
    <parameters>
      <type>object</type>
      <properties>
        <command>
          <type>string</type>
          <description>The command to execute, for example 'ls' or 'pwd'.</description>
        </command>
        <path>
          <type>string</type>
          <description>The absolute path inside the container to execute the command in, for example 'opt/' or 'home/user/'. Must end with a slash.</description>
        </path>
      </properties>
      <required>
        <item>command</item>
        <item>path</item>
      </required>
    </parameters>
  </tool>

  <tool>
    <name>search</name>
    <description>Search the web for information.</description>
    <parameters>
      <type>object</type>
      <properties>
        <query>
          <type>string</type>
          <description>The search term</description>
        </query>
      </properties>
      <required>
        <item>query</item>
      </required>
    </parameters>
  </tool>
</tools>
"""


# --- LLM call ---
def llm(question: str):
    system_prompt = f"""
You are an API function selector. Based on the user's request, you will select one of the available tools.
ONLY respond with a valid JSON tool call.

TOOLS AVAILABLE:
{tools}

Rules:
- ONLY respond with one tool.
- The JSON MUST follow the format:
{{
  "tool": {{
    "name": "<tool_name>",
    "parameters": {{ ... }}
  }}
}}

USER: {question}
"""
    response = genai_client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[system_prompt]
    )
    try:
        raw = response.text.strip()
        start = raw.find('{')
        end = raw.rfind('}') + 1
        clean_response = raw[start:end]
        formatted = json.loads(clean_response)
        return formatted
    except Exception as e:
        print("❌ Failed to parse response:", e)
        print("🧾 Raw output:\n", response.text)
        return None


# --- Tool executor ---
def execute_tool(parsed):
    if not parsed or "tool" not in parsed:
        print("❌ Invalid tool call")
        return

    tool_name = parsed["tool"]["name"]
    params = parsed["tool"]["parameters"]

    if tool_name == "execute_docker_command":
        command = params.get("command")
        path = params.get("path", "")


        api_argument = f"{command}/{path}"

        result = controller("docker/", api_argument)
        print("\n--- 🐳 Docker Command Result ---")
        print(json.dumps(result, indent=2))
        print("-----------------------------\n")

    elif tool_name == "search":
        result = controller(tool_path="search/", argument=params.get('query'))
        return result

    else:
        print(f"❌ Unknown tool: {tool_name}")


if __name__ == '__main__':
    # This prompt is designed to trigger your new docker tool.
    user_prompt = input("entrez votre question: ")

    print(f"USER PROMPT: {user_prompt}\n")

    # 1. Get the tool call from the LLM
    tool_call = llm(user_prompt)

    if tool_call:
        print(f" LLM RECOMMENDED TOOL CALL:\n{json.dumps(tool_call, indent=2)}\n")

        # 2. Execute the recommended tool
        result = execute_tool(tool_call)
        print(result)