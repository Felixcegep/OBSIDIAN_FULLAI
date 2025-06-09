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
      <step>3. Prepare the tool call by clearly filling the required parameters.</step>
      <step>4. Respond using valid JSON format with the tool name and parameters.</step>
      <step>5. Do not include explanations or commentary outside the JSON unless asked.</step>
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
        config=types.GenerateContentConfig(
            system_instruction=system_prompt),
        contents=question
    )
    print(response.text)

    parsed = json.loads(response.text[7:-4])
    print(parsed)
    return parsed

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
        contents=question
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
        # Extract the search query
        query = params["query"]
        print("Performing search for query:", query)

        # Use the controller to fetch search results
        links = controller(tool_name, query)

        if not links["searched"]:
            return "No links found from the search results."

        # Use the first result's URL to scrape content
        link = links["searched"][0]["url"]
        content = universal_scraper(link)
        print("Scraped content:\n", "$" * 70)
        print(content)

        # Summarize the scraped content using an LLM
        summary = llm_summarize(content)
        return f"Website Summary:\n{summary}"

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
    session_history = ""  # Accumulate session context across turns

    while True:
        try:
            # Get current path once per loop
            current_path = machine.get_current_path()
            info = f"User is at path: {current_path}\n"

            # Prompt the user
            question = input(f"{current_path}: ")

            if question.lower() in ["exit", "quit"]:
                print("Exiting session.")
                break

            # Prepare full context prompt for LLM
            context_prompt = session_history + info + question
            parsed = llm(context_prompt)

            # Execute the parsed tool instruction
            result = execute_tool(parsed)
            print(result)

            # Accumulate history for the next LLM turn
            session_history += f"\n> {question}\n{result}\n"

        except Exception as e:
            print("An error occurred:", str(e))
