# server.py
from fastapi import FastAPI
import uvicorn
from searxng_search import search

app = FastAPI()

# --- MOCK Docker Control Function ---
# Replace this with the import from your actual main_ubuntu.py
# from main_ubuntu import control_docker
def control_docker(path: str, command: str):
    """
    This is a mock function. It simulates executing a command in Docker.
    Replace this with your real implementation.
    """
    print(f" MOCK SERVER: Received command='{command}' for path='{path}'")
    # In a real scenario, you would execute the command and get the output.
    # For example: exit_code, output = container.exec_run(f"cd {path} && {command}")
    mock_output = f"Simulated output for '{command}' in '{path}':\n- file1.txt\n- sub_dir/\n- another_file.sh"
    return {"status": "success", "command": command, "path": path, "output": mock_output}
# ------------------------------------

@app.get("/")
async def root():
    return {"message": "Docker Control API is running"}

# This is the API endpoint you want to call
@app.get("/docker/{command}/{path:path}")
async def execute_command_in_docker(command: str, path: str):
    """
    Executes a command in the Docker container at a specific path.
    """
    # The path parameter automatically includes the leading slash if provided in the URL
    # So we pass it directly to the control function.
    result = control_docker(f"/{path}", command)
    return result
@app.get("/search/{question}")
async def read_item(question:str):
    raw_results = search(question)
    liste_topfive = []
    def clean_item(item):
        return {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", "")[:200] + "...",  # truncate long content
            "score": item.get("score", 0.0)
        }

    for item in raw_results[:5]:
        liste_topfive.append(clean_item(item))

    return {"question": question, "searched": liste_topfive}
if __name__ == "__main__":
    # To run this server: uvicorn server:app --reload
    uvicorn.run(app, host="127.0.0.1", port=8000)