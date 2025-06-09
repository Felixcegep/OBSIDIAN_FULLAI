import requests

def controller(tool: str, argument: str) -> dict:
    base_url = "http://127.0.0.1:8000/"
    full_url = f"{base_url}{tool}/{argument}"
    print("Full URL:", full_url)
    response = requests.get(full_url)
    return response.json()
