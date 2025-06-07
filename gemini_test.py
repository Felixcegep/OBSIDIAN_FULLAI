import json
import requests
import dotenv
import os
from google import genai
from requester import controller
from scraper import universal_scraper
from main_ubuntu import control_docker
import docker
# Load environment variables (ex: GEMINI_API_KEY)
dotenv.load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# --- Tool list in XML for prompt clarity ---

client = docker.from_env()

# Run Ubuntu and keep it alive
#ouvrir ubuntu
try:
    container = client.containers.run(
        "ubuntu-with-git",
        "sleep infinity",
        detach=True,
        tty=True,
        name="ubuntu_chat12"
    )
    print(f"Container '{container.name}' started.")
except docker.errors.APIError:
    container = client.containers.get("ubuntu_chat12")
    print("Container already exists. Reusing.")


tools = """
<tools>
  
  <tool>
    <name>search</name>
    <description>Search something on the backend server.</description>
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
You are an API function selector. ONLY respond with a valid JSON tool call.

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

    response = client.models.generate_content(
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


    if tool_name == "search":
        user_choice = []
        topfive = controller(tool="search/", argument=params.get("query", ""))
        for i, item in enumerate(topfive["searched"]):
            print(i, item["url"],item["title"],item["content"])
        choice = int(input("choice : "))
        print("your choice ", topfive["searched"][choice]["url"])
        content = universal_scraper(topfive["searched"][choice]["url"])
        print(content)
##
    else:
        print(f"❌ Unknown tool: {tool_name}")

