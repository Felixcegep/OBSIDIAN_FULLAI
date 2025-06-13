from fastapi import FastAPI
from searxng import search

app = FastAPI()

@app.get("/")
async def read_root():

    return {"message": "Hello, aaaa!"}
@app.get("/Search")
async def read_item(question: str):
    print("questions :", question)
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


@app.get("/docker/{command}")
async def execute_command(command: str):
    print("Executing command:", command)
    return command




