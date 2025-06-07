import docker

client = docker.from_env()

# Run Ubuntu and keep it alive
try:
    container = client.containers.run(
        "ubuntu-with-git",
        "sleep infinity",
        detach=True,
        tty=True,
        name="ubuntu_chat12"
    )
    print(f"Container '{container.name}' started.")
except docker.errors.APIError:
    container = client.containers.get("ubuntu_chat12")
    print("Container already exists. Reusing.")



def control_docker(current_path: str, question: str) -> dict:
    """
    Contrôle un conteneur Docker en exécutant une commande à l'intérieur et retourne une réponse JSON.
    """
    if question.strip() == "quit":
        container.remove(force=True)
        return {
            "path": current_path,
            "command": question,
            "output": "Container removed.",
            "status": "terminated"
        }

    elif question.startswith("cd"):
        parts = question.strip().split()
        if len(parts) < 2:
            return {
                "path": current_path,
                "command": question,
                "output": "Usage: cd <path>",
                "status": "error"
            }

        cmd = f"bash -c 'cd \"{current_path}\" && cd \"{parts[1]}\" && pwd'"
        exec_result = container.exec_run(cmd)
        output = exec_result.output.decode(errors="ignore").strip()

        if exec_result.exit_code == 0:
            return {
                "path": output,
                "command": question,
                "output": f"Changed directory to {output}",
                "status": "success"
            }
        else:
            return {
                "path": current_path,
                "command": question,
                "output": output or "Failed to change directory.",
                "status": "error"
            }

    else:
        cmd = f"bash -c 'cd \"{current_path}\" && {question}'"
        exec_result = container.exec_run(cmd, tty=True)
        output = exec_result.output.decode(errors="ignore").strip()

        return {
            "path": current_path,
            "command": question,
            "output": output,
            "status": "success" if exec_result.exit_code == 0 else "error"
        }


if __name__ == '__main__':

    # Initial working directory
    path = "/opt/FMHY-RAG"
    while True:
        try:
            question = input(">>> ")
            path = control_docker(path, question)
        except KeyboardInterrupt:
            print("\nExiting.")
            break
