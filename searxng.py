import requests
import dotenv

dotenv.load_dotenv()


def search(question : str):
    url = "http://127.0.0.1:8080/search"
    headers = {"Accept": "application/json"}
    params = {
        "q": question,
        "categories": "general",
        "format": "json"
    }
    response = requests.get(url, params=params, headers=headers)
    data = response.json()
    return data["results"]
