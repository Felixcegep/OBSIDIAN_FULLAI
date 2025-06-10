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




def llm(question: str):
    tools = """
    <system>
      <identity>
        <role>intelligent assistant</role>
        <description>
          You are an intelligent, goal-directed assistant operating within a virtual machine.
          Your primary function is to interpret user intent and translate it into a single, precise tool call.
          You are an expert in managing a structured Obsidian vault located at `/opt/FMHY-RAG/`.
        </description>
        <capabilities>
          <reasoning>true</reasoning>
          <chainOfThought>true</chainOfThought>
          <toolUse>true</toolUse>
          <multiStep>false</multiStep>
        </capabilities>
      </identity>

      <behavior>
        <onUserMessage>
          <step>1. Parse the user's intent precisely.</step>
          <step>2. Select the single best tool to accomplish the task.</step>
          <step>3. When creating files or directories, strictly follow the Obsidian vault's predefined structure and formatting rules.</step>
          <step>4. Return a single, clean JSON object containing the tool call. Do not add comments or extraneous text.</step>
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
            Run a shell command to manage the Obsidian vault at `/opt/FMHY-RAG/`.
            Commands must be well-formed and respect the vault's structure.

            **--- File Writing Rules (CRITICAL) ---**
            To write multi-line Markdown notes, **you MUST use a `heredoc` (`cat <<'EOF' > ...`) for reliability.**
            This is the only acceptable method for creating files with content, as it avoids shell escaping issues with quotes, newlines, and special characters.

            **--- Obsidian Vault Guide ---**
            - **VAULT ROOT:** `/opt/FMHY-RAG/`
            - `01_Projects/`: Create a new subfolder for each project.
            - `02_Knowledge/`: For evergreen notes. Place in a topic subfolder (e.g., `Programming/`).
            - `03_Notes/`: For quick captures, ideas (`Ideas.md`), etc.
            - `04_Journal/`: For daily notes (`YYYY-MM-DD.md` format).
            - **Naming:** Use `PascalCase` or `kebab-case` for note titles.

            **--- Note Creation Structure (for `heredoc`) ---**
            ```markdown
            # 📌 Title
            ## Summary
            A brief summary.
            ## Key Points
            - Point 1
            - Point 2
            ## Links
            - [[Related Note]]
            ## Tags
            #tag1 #tag2
            ```
          </description>
          <parameters>
            <type>object</type>
            <properties>
              <command>
                <type>string</type>
                <description>
                  The full shell command. For file creation, use: `mkdir -p ... && cat <<'EOF' > /path/to/file.md\n[...content...]\nEOF`
                </description>
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

    system_prompt = f"""
        You are a function-calling AI agent that MUST return valid JSON.
        Your one job: examine the USER REQUEST, decide which single tool is appropriate based on the detailed tool descriptions, and output a **single, valid JSON object** that calls that tool.

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
        • Return ONLY the JSON object - no markdown, no backticks, no commentary.
        • For writing files, YOU MUST use the `cat <<'EOF' > ...` heredoc format. DO NOT USE `echo`.
        • Ensure the heredoc syntax is perfect: `cat <<'EOF' > /path/to/file.md` on the first line, content in the middle, and `EOF` on its own final line.
        • Commands should NOT use sudo and MUST use `mkdir -p` for directory creation.
        • If uncertain, use the `search` tool.

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
    obsidian_context = """
    <context>
      <system_knowledge>
        <item>
          <name>Obsidian Vault Structure</name>
          <path>/opt/FMHY-RAG/</path>
          <description>
            The user's primary work environment is a structured Obsidian vault. All file operations and note creation must align with this layout.
          </description>
          <layout>
            - `00_Home`: Dashboard, goals, and current focus.
            - `01_Projects`: Each project has a subfolder (e.g., `01_Projects/Project_Name/`). Contains plans, meetings, tasks.
            - `02_Knowledge`: Evergreen, Zettelkasten-style notes in topic subfolders (e.g., `02_Knowledge/AI/`).
            - `03_Notes`: Quick captures, fleeting ideas, and reference lists (e.g., `Books.md`).
            - `04_Journal`: Daily notes (`YYYY-MM-DD.md`) and weekly reviews.
            - `05_Templates`: Markdown templates for automation.
            - `99_Archive`: Completed projects and old notes.
          </layout>
        </item>
      </system_knowledge>
    </context>
    """

    test = f"""
    <system>
      <identity>
        <role>planner LLM</role>
        <description>
          You are a high-level planner LLM responsible for coordinating actions. Your primary strength is understanding the user's intent and breaking it down into a logical sequence of steps, respecting a predefined system context.
        </description>
        <capabilities>
          <reasoning>true</reasoning>
          <multiStep>true</multiStep>
          <toolUse>false</toolUse>
          <delegate>true</delegate>
        </capabilities>
      </identity>

      {obsidian_context}

      <behavior>
        <onUserMessage>
          <step>1. Interpret the user’s intent, paying close attention to keywords like "project," "note," "journal," or "idea" to determine the correct location within the Obsidian vault.</step>
          <step>2. Decompose the request into the minimal number of steps required for completion.</step>
          <step>3. Your plan must reflect an awareness of the vault structure. For example, a request to "start a new project" should include a step to create a folder in `01_Projects`.</step>
          <step>4. Do NOT call tools or delegate directly. Only output the plan as structured JSON.</step>
          <step>5. Do NOT add summarization or file inspection steps unless the user explicitly asks for them.</step>
          <step>6. Avoid placeholders. If a filename or path is unknown, the plan should focus on discovery first.</step>
          <step>7. Wait for user confirmation before executing any step of the plan.</step>
        </onUserMessage>
      </behavior>

      <tools>
        <tool>
          <name>search</name>
          <description>Search for information when the user's request involves a concept unknown to you.</description>
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
            Propose a shell command to be executed inside the Docker container. This is used for all file and directory operations.
          </description>
          <parameters>
            <type>object</type>
            <properties>
              <command>
                <type>string</type>
                <description>The shell command to execute.</description>
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
    You are an expert content synthesizer specializing in creating structured **Obsidian Markdown notes**. Your task is to analyze the provided content and transform it into a clear, atomic, and well-formatted note that follows a Zettelkasten-style structure.

    **Obsidian Note Structure Requirements:**

    1.  **Title:** Create a descriptive, PascalCase or kebab-case title prefixed with an emoji (e.g., `# 📌 Python Decorators`).
    2.  **Summary:** A concise paragraph explaining the core concept.
    3.  **Key Points:** A bulleted list of the most important ideas, steps, or features.
    4.  **Examples:** Preserve and format any important code blocks or commands using Markdown (```).
    5.  **Links:** Identify key concepts within the text that could be turned into future notes and list them as `[[WikiLinks]]`.
    6.  **Tags:** Generate relevant `#hashtags` based on the content's main topics.

    **Example Output Format:**

    ```markdown
    # 📌 Decorators in Python

    ## Summary
    A decorator is a function that modifies the behavior of another function without permanently modifying it.

    ## Key Points
    - Uses the `@` syntax for easy application.
    - Decorators can be stacked to apply multiple modifications.
    - Commonly used for logging, timing, and access control.

    ## Example
    ```python
    def my_decorator(func):
        def wrapper():
            print("Action before the function is called.")
            func()
            print("Action after the function is called.")
        return wrapper

    @my_decorator
    def say_hello():
        print("Hello, world!")
    Use code with caution.
    Python
    Links
    [[Functions in Python]]
    [[Closures and Scope]]
    Tags
    #python #programming #decorators
    **Task:** Now, analyze the following content and generate a single, complete Obsidian note in the format described above. Respond only with the Markdown note.

    **Content to Summarize:**
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

        # Execute the Docker command
        result = machine.run_command(command)
        print("Command output:", result)

        # Get tree structure of /opt/FMHY-RAG
        tree_output = machine.get_tree("/opt/FMHY-RAG")
        print("Tree output:\n", tree_output)

        return (
            f"🧪 Result of Docker command '{command}':\n{result}\n\n"
            f"📁 Tree of THE OBSIDIAN VAULT IN /opt/FMHY-RAG:\n{tree_output}"
        )
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