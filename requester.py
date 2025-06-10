import requests

def controller(tool: str, argument: str) -> dict:
    base_url = "http://127.0.0.1:8000/"

    if tool == "search":
        full_url = f"{base_url}{tool}?question={argument}"
    else:
        full_url = f"{base_url}{tool}/{argument}"

    print("Full URL:", full_url)
    response = requests.get(full_url)
    return response.json()