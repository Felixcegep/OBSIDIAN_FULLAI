import requests
def controller(tool: str, argument):
    base_url = "http://127.0.0.1:8000/"
    full_url = base_url + tool + argument
    response = requests.get(full_url)
    return response.json()
