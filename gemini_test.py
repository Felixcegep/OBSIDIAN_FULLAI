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
      You are an intelligent, goal-directed assistant operating within a virtual machine.
      Your primary function is to interpret user intent, reason through steps, and delegate execution to tools when necessary.
      The VM is already updated—do not attempt apt upgrade or system updates.
      Tool use must be efficient, minimal, and deliberate.
      When writing to files, you specialize in generating well-structured Obsidian Markdown notes.
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
      <step>1. Parse the user's intent precisely.</step>
      <step>2. Determine if a tool is required to satisfy the request.</step>
      <step>3. Only use the <search> tool if the concept is unknown or execution fails unexpectedly.</step>
      <step>4. When using a tool, return a strict JSON object that includes only the tool name and required parameters.</step>
      <step>5. Do not add comments, markdown, or plain text responses unless explicitly requested.</step>
    </onUserMessage>
  </behavior>

  <tools>
    <tool>
      <name>search</name>
      <description>
        Query the backend search system for information not known to the model or when errors require external troubleshooting.
      </description>
      <parameters>
        <type>object</type>
        <properties>
          <query>
            <type>string</type>
            <description>The search term or question to resolve the user's request.</description>
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
        Run a shell command within the Docker environment. Commands must be well-formed; this tool does not infer intent or sanitize input.
        When writing text files, all content must be correctly formatted in **Markdown** optimized for Obsidian.
        Follow these rules:
        - Use `#` for headers (`#`, `##`, `###`, etc.)
        - Use `-` for bullet lists, `1.` for numbered lists
        - Enclose code in triple backticks (```) for code blocks
        - Bold using `**`, italic using `_`
        - Prefer `echo -e` or heredocs for writing multi-line notes
        - Escape all quotes and newlines properly (e.g., `\"`, `\\n`)
        Output should be short, clean, and suitable for insertion into `.md` files inside an Obsidian vault.
      </description>
      <parameters>
        <type>object</type>
        <properties>
          <command>
            <type>string</type>
            <description>The full shell command to run (e.g., 'ls /opt', 'echo -e "# Title\\n\\n**Bold text**" > doc.md').</description>
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
    You are a function-calling AI agent that MUST return valid JSON.
    Your one job: examine the USER REQUEST, decide which single tool is appropriate, and output a **single, valid JSON object** that calls that tool.

    TOOLS AVAILABLE:
    {tools}

    ──────────────────────── RESPONSE FORMAT ────────────────────────
    Return ONLY a single JSON object with this exact structure:

    {{
      "tool": {{
        "name": "<tool_name>",
        "parameters": {{
          ... appropriate parameters ...
        }}
      }}
    }}

    ──────────────────────── STRICT RULES ───────────────────────────
    CRITICAL:
    • Return ONLY the JSON object - no markdown, no backticks, no commentary
    • Every string value MUST be properly quoted
    • If you're uncertain about the task, use the search tool with the user's question as the query
    • Commands should NOT use sudo (assume root access)
    • Always use mkdir -p for directory creation

    TOOL SELECTION:
    • Use "search" for: new concepts, troubleshooting, unknown information
    • Use "execute_docker_command" for: file operations, system commands, running programs

    USER REQUEST:
    {question}
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            config=types.GenerateContentConfig(
                system_instruction=system_prompt),
            contents=question
        )

        # Clean the response text
        response_text = response.text.strip()

        # Remove common markdown artifacts
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        if response_text.startswith("```"):
            response_text = response_text[3:]

        response_text = response_text.strip()

        # Try to parse the JSON
        parsed = json.loads(response_text)
        print("Parsed successfully:", parsed)
        return parsed

    except json.JSONDecodeError:
        # If JSON parsing fails, fall back to search
        print(f"JSON parsing failed, falling back to search for: {question}")
        return {
            "tool": {
                "name": "search",
                "parameters": {
                    "query": question
                }
            }
        }
    except Exception as e:
        # For any other error, also fall back to search
        print(f"Unexpected error, falling back to search for: {question}")
        return {
            "tool": {
                "name": "search",
                "parameters": {
                    "query": question
                }
            }
        }

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
        print("wow",result)
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
            print(result)
            session_history += f"\n> {question}\n{result}\n"