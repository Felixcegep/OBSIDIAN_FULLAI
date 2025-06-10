import json
import requests
import dotenv
import os
from google import genai
from google.genai import types

from requester import controller
from scraper import universal_scraper
from main_ubuntu import DockerShell
import docker
dotenv.load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# --- Tool list in XML for prompt clarity ---
machine = DockerShell()


tools = """
<system>
  <identity>
    <role>intelligent assistant</role>
    <description>
      You are a smart assistant capable of interpreting user messages, reasoning step by step, and deciding when to call tools.
      The virtual machine (VM) you are working with is already up to date, so there is no need to run apt upgrade or system update commands.
      Only use the search tool when the task involves a new concept you haven't seen before or when a problem arises that cannot be solved directly.
      You always return tool calls in valid JSON format. Never return plain text or raw commands unless explicitly requested.
    </description>
    <capabilities>
      <reasoning>true</reasoning>
      <chainOfThought>true</chainOfThought>
      <toolUse>true</toolUse>
      <multiStep>true</multiStep>
    </capabilities>
  </identity>

  <behavior>
    <onUserMessage>
      <step>1. Understand the user's intent from the message.</step>
      <step>2. If a tool is needed, decide which one best fits the task.</step>
      <step>3. Only use the search tool if the information is not known or if an error needs external troubleshooting.</step>
      <step>4. Prepare the tool call by clearly filling the required parameters.</step>
      <step>5. Respond using valid JSON format with the tool name and parameters.</step>
      <step>6. Do not include explanations or commentary outside the JSON unless asked.</step>
    </onUserMessage>
  </behavior>

  <tools>
    <tool>
      <name>search</name>
      <description>Search something on the backend server based on a given query. Only use if the concept is new or if a known method fails.</description>
      <parameters>
        <type>object</type>
        <properties>
          <query>
            <type>string</type>
            <description>The search term or question to query.</description>
          </query>
        </properties>
        <required>
          <item>query</item>
        </required>
      </parameters>
    </tool>

    <tool>
      <name>execute_docker_command</name>
      <description>
        Execute a shell command inside a running Docker container. The tool does not infer intent—commands must be precise.
      </description>
      <parameters>
        <type>object</type>
        <properties>
          <command>
            <type>string</type>
            <description>The shell command to execute (e.g., 'ls', 'cat file.txt').</description>
          </command>
        </properties>
        <required>
          <item>command</item>
        </required>
      </parameters>
    </tool>
  </tools>
</system>

"""



def llm(question: str):
    system_prompt = f"""
    You are a function-calling AI agent. Your only task is to select **one** tool from the list below and respond using the exact JSON structure provided.

    TOOLS AVAILABLE:
    {tools}

    RESPONSE FORMAT:
    You MUST respond with exactly one tool call in **valid JSON**, and nothing else. The format is:

    {{
      "tool": {{
        "name": "<tool_name>",
        "parameters": {{
          ... appropriate parameters ...
        }}
      }}
    }}

    STRICT RULES:
    - You must return a single valid JSON object exactly in the format described above.
    - Do NOT explain your choice.
    - Do NOT add any commentary, disclaimers, or error messages — respond with JSON only.
    - Do NOT wrap the JSON in Markdown, triple backticks, or quotes.
    - All values MUST be properly quoted if they are strings.
    - The JSON must be syntactically valid and directly parseable by `json.loads()`.
    - NEVER use `sudo` in any command. Assume all commands will be executed as root.
    - When creating directories using `mkdir`, always use the `-p` option (i.e., `mkdir -p`) to prevent errors if the directory already exists.
    - If you're unsure what to do, default to using the `search` tool with the user's request as the query.

    EXAMPLE RESPONSE:
    {{
      "tool": {{
        "name": "execute_docker_command",
        "parameters": {{
          "command": "mkdir -p /opt/my_folder"
        }}
      }}
    }}

    USER REQUEST:
    {question}
    """

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        config=types.GenerateContentConfig(
            system_instruction=system_prompt),
        contents=question
    )

    try:
        parsed = json.loads(response.text[7:-4])
        print(parsed)
        return parsed
    except json.decoder.JSONDecodeError:
        return f"erreur {response.text} is not a valid JSON object"

def the_planner(question: str):
    test = """
   <system>
  <identity>
    <role>planner LLM</role>
    <description>
      You are a high-level planner LLM responsible for coordinating actions between available tools and the Slave LLM.
      Your job is to decide what specific information or command is needed, when to call tools like 'search' or 'execute_docker_command',
      and to break down complex tasks into efficient, minimal, and necessary steps.
    </description>
    <capabilities>
      <reasoning>true</reasoning>
      <multiStep>true</multiStep>
      <toolUse>true</toolUse>
      <delegate>true</delegate>
    </capabilities>
  </identity>

  <behavior>
    <onUserMessage>
      <step>1. Interpret the user’s intent clearly and concisely.</step>
      <step>2. Only generate steps that are essential to fulfill the user's actual request.</step>
      <step>3. Do NOT add summarization, file analysis, or inspection steps unless the user explicitly requests them.</step>
      <step>4. Avoid placeholders like &lt;filename&gt;. If the filename is not known or requested, do not attempt to read files.</step>
      <step>5. Do NOT call tools or delegate directly. Only output the plan as structured JSON.</step>
      <step>6. Ensure the number of steps is minimal and directly aligned with user intent.</step>
      <step>7. Wait for user confirmation before executing any step of the plan.</step>
    </onUserMessage>
  </behavior>

  <tools>
    <tool>
      <name>search</name>
      <description>Search something on the backend server based on a given query.</description>
      <parameters>
        <type>object</type>
        <properties>
          <query>
            <type>string</type>
            <description>The search term or question to query.</description>
          </query>
        </properties>
        <required>
          <item>query</item>
        </required>
      </parameters>
    </tool>

    <tool>
      <name>execute_docker_command</name>
      <description>
        Execute a shell command inside a running Docker container. You must provide precise and self-contained commands.
      </description>
      <parameters>
        <type>object</type>
        <properties>
          <command>
            <type>string</type>
            <description>The shell command to execute in the container.</description>
          </command>
        </properties>
        <required>
          <item>command</item>
        </required>
      </parameters>
    </tool>
  </tools>

  <delegation>
    <slave>
      <name>slave LLM</name>
      <description>Handles specific reasoning, summarization, or content generation when explicitly asked by the user.</description>
    </slave>
  </delegation>
</system>

    """
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        config=types.GenerateContentConfig(
            system_instruction=test),
        contents=question
    )
    unformated = response.text
    try:
        formater = json.loads(unformated[7:-4])
        return formater
    except json.decoder.JSONDecodeError:
        return "formated wrong"

def llm_summarize(content : str):
    system_instruction_summary = f"""
You are a web content summarizer. Your job is to analyze and summarize the following web content into a clear, structured, and concise summary.

Requirements:
- Identify the main purpose of the page (e.g., tutorial, documentation, announcement).
- Summarize step-by-step instructions, lists, or tips if present.
- Omit unnecessary repetition and verbose details.
- Keep the tone neutral and informative.
- If the content includes commands or code, preserve the most important ones.

Respond only with the summary. Do not repeat the input text. If the content is too technical or dense, group steps under headers.

Begin summarizing the following content:

"""
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        config=types.GenerateContentConfig(
            system_instruction=system_instruction_summary),
        contents=content
    )
    return response.text
# --- Tool executor ---
def execute_tool(parsed):
    # Print the incoming tool schema for debugging
    print("Tool schema received:", parsed)

    tool = parsed["tool"]
    tool_name = tool["name"]
    params = tool["parameters"]

    if tool_name == "search":
        # Get search results using controller
        links = controller(parsed["tool"]["name"], parsed["tool"]["parameters"]["query"])

        # Use the first search result's URL
        print("linkkkkkks",links)

        link_test = links["searched"][0]["url"]

        # Scrape content from the URL
        content = universal_scraper(link_test)


        # Summarize the content using LLM
        resume = llm_summarize(content)

        # Return the summary
        return f"resume website : {resume}"


    elif tool_name == "execute_docker_command":
        # Extract the Docker command to run
        command = params["command"]
        print("Running Docker command:", command)

        # Optional: show the constructed URL (if using an API)
        url = f"http://127.0.0.1:8000/docker/{command}"
        print("API Endpoint:", url)

        # Execute the Docker command using a helper (must be defined)
        result = machine.run_command(command)
        return f"Result of Docker command '{command}':\n{result}"

    else:
        return f"Error: Unknown tool name '{tool_name}'."


if __name__ == '__main__':
    while True:
        session_history = ""  # Accumulate session context across turns
        current_path = machine.get_current_path()
        info = f"User is at path: {current_path}\n"
        question = input(f"{current_path}: ")
        steps = the_planner(question)
        for i,step in enumerate(steps["plan"]):
            print(i,step)

        for step in steps["plan"]:
            step_llm = str(step)
            context_prompt = session_history + info + question
            parsed = llm(context_prompt)
            result = execute_tool(parsed)
            print("result", result)
            session_history += f"\n> {question}\n{result}\n"