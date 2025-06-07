from fastapi import FastAPI
from pydantic import BaseModel
from searxng_search import search
app = FastAPI()
def test():
    print("yoool")

@app.get("/")
async def read_root():
    test()
    return {"message": "Hello, dasd!"}
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


