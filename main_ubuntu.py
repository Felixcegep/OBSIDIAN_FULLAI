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



def control_docker(current_path: str, question: str) -> str:
    if question.strip() == "quit":
        container.remove(force=True)
        print("Container removed.")
        exit(0)

    elif question.startswith("cd"):
        parts = question.strip().split()
        if len(parts) < 2:
            print("Usage: cd <path>")
            return current_path

        # Execute cd and get the new path in one command
        cmd = f"bash -c 'cd \"{current_path}\" && cd \"{parts[1]}\" && pwd'"
        exec_result = container.exec_run(cmd)
        output = exec_result.output.decode(errors="ignore").strip()

        if exec_result.exit_code == 0:
            return output
        else:
            print(f"cd: {parts[1]}: No such file or directory")
            return current_path

    else:
        cmd = f"bash -c 'cd \"{current_path}\" && {question}'"
        exec_result = container.exec_run(cmd, tty=True)
        print(exec_result.output.decode(errors="ignore"))

    return current_path

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
