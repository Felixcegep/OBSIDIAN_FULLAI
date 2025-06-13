import json
import requests
import dotenv
import os
from google import genai
from google.genai import types

from scraper import universal_scraper
from container import DockerShell
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
          <name>Search</name>
          <description>
            Query the backend Search system for information not known to the model or when errors require external troubleshooting.
          </description>
          <parameters>
            <type>object</type>
            <properties>
              <query>
                <type>string</type>
                <description>The Search term or question to resolve the user's request.</description>
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

            ⚠️ CRITICAL: To write multi-line Markdown notes, use only this format:

            mkdir -p /opt/FMHY-RAG/... && cat <<'EOF' > /opt/FMHY-RAG/.../Note.md
            # 📌 Title
            ## Summary
            A brief summary.
            ## Key Points
            - One
            - Two
            ## Links
            - [[Related Note]]
            ## Tags
            #tag1 #tag2
            EOF

            ❌ NEVER use `echo` for multi-line content.
            ❌ NEVER use `sudo`.

            VAULT STRUCTURE:
            - /opt/FMHY-RAG/01_Projects/
            - /opt/FMHY-RAG/02_Knowledge/
            - /opt/FMHY-RAG/03_Notes/
            - /opt/FMHY-RAG/04_Journal/
            - /opt/FMHY-RAG/05_Templates/

            Naming: use PascalCase or kebab-case for file names.
          </description>
          <parameters>
            <type>object</type>
            <properties>
              <command>
                <type>string</type>
                <description>
                  Full shell command. Must include `mkdir -p` if necessary, and heredoc format with `cat <<'EOF' > ...`.
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
    • If uncertain, use the `Search` tool.

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
        # If JSON parsing fails, fall back to Search
        print(f"JSON parsing failed, falling back to Search for: {question}")
        return {
            "tool": {
                "name": "Search",
                "parameters": {
                    "query": question
                }
            }
        }
    except Exception as e:
        # For any other error, also fall back to Search
        print(f"Unexpected error, falling back to Search for: {question}")
        return {
            "tool": {
                "name": "Search",
                "parameters": {
                    "query": question
                }
            }
        }

def the_planner(question: str):


    system_prompt = f"""
<system>
  <identity>
    <role>planner LLM</role>
    <description>
      You are a high-level planner LLM responsible for turning user intent into
      an ordered action plan. You never run code yourself; you only output
      structured JSON plans that downstream agents will follow.
    </description>
    <capabilities>
      <reasoning>true</reasoning>
      <multiStep>true</multiStep>
      <toolUse>false</toolUse>
      <delegate>true</delegate>
    </capabilities>
  </identity>

  <!-- ─────────── Obsidian vault context ─────────── -->
  <context>
    <system_knowledge>
      <item>
        <name>Obsidian Vault Structure</name>
        <path>/opt/FMHY-RAG/</path>
        <description>
          The user’s primary workspace is a structured Obsidian vault.
          All file operations and note creation must respect this layout.
        </description>
        <layout>
          - `00_Home`: Dashboard, goals, and current focus.  
          - `01_Projects`: One subfolder per project (`01_Projects/<Project_Name>/`).  
          - `02_Knowledge`: Evergreen, Zettelkasten-style notes in topic subfolders.  
          - `03_Notes`: Quick captures and reference lists.  
          - `04_Journal`: Daily (`YYYY-MM-DD.md`) and weekly review notes.  
          - `05_Templates`: Markdown templates for automation.  
          - `99_Archive`: Completed projects and old notes.  
        </layout>
      </item>
    </system_knowledge>
  </context>

  <!-- ─────────── Runtime behaviour ─────────── -->
  <behavior>
    <onUserMessage>
      <!-- Intent & routing -->
      <step>1. Detect intent and map it to the correct vault location.  
             Look for keywords like “project”, “note”, “journal”, “idea”, as well as
             “delete”, “remove”, “trash”, “rm” for file-removal requests.</step>

      <!-- Decomposition -->
      <step>2. Break the request into the minimal, logically ordered steps.</step>

      <!-- Link integrity -->
      <step>3. Ensure every Obsidian link (e.g. <code>[[Domestication]]</code>)
             targets an existing file; if missing, add a discovery step first.</step>

      <!-- Vault awareness -->
      <step>4. Reflect vault structure in the plan
             (e.g. a new project ⇒ create folder under <code>01_Projects</code>).</step>

      <!-- File-removal policy -->
      <step>5. If the user wants to delete or remove a file:
              <substep>a. Plan a <code>execute_docker_command</code> step that
                        searches the vault, e.g.  
                        <code>find /opt/FMHY-RAG -type f -name "&lt;file&gt;"</code>,
                        capturing the full path.</substep>
              <substep>b. After path discovery and user confirmation, plan the
                        removal (move to <code>99_Archive</code> or
                        <code>rm &lt;full_path&gt;</code>).</substep></step>

      <!-- Tool usage constraints -->
      <step>6. Do <strong>not</strong> call tools or delegate directly; only output
             the plan in structured JSON.</step>

      <!-- Extraneous work -->
      <step>7. Do <strong>not</strong> add summarization or file-inspection steps
             unless explicitly requested.</step>

      <!-- Unknowns -->
      <step>8. Avoid placeholders; if something is unknown, plan discovery first.</step>

      <!-- Confirmation -->
      <step>9. Always wait for explicit user confirmation before executing any
             step of the plan.</step>
    </onUserMessage>
  </behavior>

  <!-- ─────────── Available tools ─────────── -->
  <tools>
    <tool>
      <name>Search</name>
      <description>Query the Internet when external knowledge is required.</description>
      <parameters>
        <type>object</type>
        <properties>
          <query>
            <type>string</type>
            <description>The search term or question.</description>
          </query>
        </properties>
        <required><item>query</item></required>
      </parameters>
    </tool>

    <tool>
      <name>execute_docker_command</name>
      <description>
        Propose a shell command (e.g., <code>find</code>, <code>grep</code>, <code>mkdir</code>, <code>rm</code>)
        to be executed inside the container for all file and directory operations.
      </description>
      <parameters>
        <type>object</type>
        <properties>
          <command>
            <type>string</type>
            <description>The exact shell command.</description>
          </command>
        </properties>
        <required><item>command</item></required>
      </parameters>
    </tool>
  </tools>

  <!-- ─────────── Delegation policy ─────────── -->
  <delegation>
    <slave>
      <name>slave LLM</name>
      <description>
        Handles detailed reasoning, summarisation, or content generation when
        explicitly instructed by the user or the planner.
      </description>
    </slave>
  </delegation>
</system>


    """
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        config=types.GenerateContentConfig(
            system_instruction=system_prompt),
        contents=question
    )
    unformated = response.text
    try:
        formater = json.loads(unformated[7:-4])
        return formater
    except json.decoder.JSONDecodeError:
        return "formated wrong"

def llm_summarize(content: str) -> str:
    """Summarize arbitrary content into a single, well‑structured Obsidian note.

    The generated note follows a Zettelkasten‑friendly template and *only* links to
    notes that already exist in the vault at /opt/FMHY‑RAG.
    """

    # 1) Inspect the current vault so the model knows which links are valid
    vault_tree = machine.get_tree("/opt/FMHY-RAG")


    # 2) System prompt with strict formatting + link‑validation rule
    system_instruction_summary = f"""
    <system>
      <identity>
        <role>content-synthesizer</role>
        <description>
          You are an expert content synthesizer who converts arbitrary text into a
          single, atomic Obsidian Markdown note that follows Zettelkasten principles.
        </description>
        <capabilities>
          <reasoning>true</reasoning>
          <multiStep>false</multiStep>
          <toolUse>false</toolUse>
        </capabilities>
      </identity>

      <behavior>
        <onUserMessage>
          <step>1. Parse the user-provided content.</step>
          <step>2. Produce ONE complete Markdown note with the structure below.</step>
          <step>3. When creating links, <strong>only</strong> link to the filenames listed in the
                  “Allowed note titles” block (case-sensitive, no “.md” extension).
                  Do <strong>not</strong> link to folders or any other names.</step>
          <step>4. Respond with nothing except the finished Markdown note.</step>
        </onUserMessage>
      </behavior>

      <!-- ──────────────────────────────────────────────────────────────── -->
      <!--              Obsidian Note Structure Requirements               -->
      <!-- ──────────────────────────────────────────────────────────────── -->
      <instructions>
        You must follow this template:

        1. <strong>Title</strong> – PascalCase or kebab-case, prefixed with an emoji
           (e.g., <code># 📌 Python-Decorators</code>).
        2. <strong>Summary</strong> – one concise paragraph.
        3. <strong>Key Points</strong> – bulleted list of core ideas.
        4. <strong>Examples</strong> – fenced code blocks where relevant.
        5. <strong>Links</strong> – only <code>[[WikiLinks]]</code> to allowed note titles.
        6. <strong>Tags</strong> – relevant <code>#hashtags</code>.
      </instructions>

      <!-- ──────────────────────────────────────────────────────────────── -->
      <!--           Allowed note titles (link whitelist)                  -->
      <!-- ──────────────────────────────────────────────────────────────── -->
      <allowedNoteTitles>
        templates
        note
        Cat
        Blocking-Bypassing-Captchas-reCAPTCHAs
        project
        journal
        CodingSession
        knowledge
        Solving-Amazon-Flex-Captcha-Issues
        home
      </allowedNoteTitles>

      <!-- Full vault tree shown for reference; do not link to folders. -->
      <vaultTree>
    |--- 05_Templates
    |   |--- templates.md
    |--- .obsidian
    |   |--- app.json
    |--- 03_Notes
    |   |--- note.md
    |   |--- Cat.md
    |   |--- Blocking-Bypassing-Captchas-reCAPTCHAs.md
    |--- 01_Projects
    |   |--- project.md
    |--- 04_Journal
    |   |--- journal.md
    |   |--- CodingSession.md
    |--- 02_Knowledge
    |   |--- knowledge.md
    |   |--- Web-Scraping
    |   |--- Animals
    |   |--- LinuxCommands
    |   |--- Development
    |   |--- Solving-Amazon-Flex-Captcha-Issues.md
    |   |--- Dinosaurs
    |   |--- Paleontology
    |   |--- Biology
    |--- 00_Home
    |   |--- home.md
      </vaultTree>

      <!-- ──────────────────────────────────────────────────────────────── -->
      <!--                     Example output format                       -->
      <!-- ──────────────────────────────────────────────────────────────── -->
      <example>
    ```markdown
    # 📌 Decorators-in-Python

    ## Summary
    A decorator is a function that modifies the behaviour of another function without permanently changing it.

    ## Key Points
    - Uses the `@` syntax for simple application.
    - Multiple decorators can be stacked.
    - Typical use-cases: logging, timing, access control.

    ## Example
    ```python
    @my_decorator
    def say_hello():
        print("Hello, world!")
    Links
    [[Functions-in-Python]]
    [[Closures-and-Scope]]

    Tags
    #python #programming #decorators

    pgsql
    Copy
    Edit
      </example>

      <finalTask>
        Analyse the content supplied by the user and output ONE complete Markdown
        note that obeys all rules above. Do <strong>not</strong> wrap your answer in XML—return
        only the Markdown.
      </finalTask>
    </system>
    """

    # 3) Call Gemini with the enhanced system instruction
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        config=types.GenerateContentConfig(system_instruction=system_instruction_summary),
        contents=content,
    )

    return response.text
# --- Tool executor ---
def execute_tool(parsed):

    print("Tool schema received:", parsed)

    tool = parsed["tool"]
    tool_name = tool["name"]
    params = tool["parameters"]

    if tool_name == "Search":
        # Get Search results using controller
        base_url = "http://127.0.0.1:8000/"
        full_url = f"{base_url}{parsed["tool"]["name"]}?question={parsed["tool"]["parameters"]["query"]}"

        response = requests.get(full_url)

        links = response.json()

        # Use the first Search result's URL

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


        # Execute the Docker command
        result = machine.run_command(command)
        print("Command output:", result)

        # Get tree structure of /opt/FMHY-RAG
        tree_output = machine.get_tree("/opt/FMHY-RAG")

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

        for i,step in enumerate(steps["plan"]):
            step_llm = str(step)
            context_prompt = session_history + info + question
            parsed = llm(context_prompt)
            result = execute_tool(parsed)
            print("--------------------------")
            print(i,result)
            session_history += f"\n> {question}\n{result}\n"
