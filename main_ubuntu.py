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
new_path = "/"

while True:
    question = input(new_path + ": ")

    if question.strip() == "quit":
        container.remove(force=True)
        break

    elif question.startswith("cd"):
        parts = question.strip().split()
        if len(parts) < 2:
            print("Usage: cd <path>")
            continue

        test = container.exec_run(f"bash -c 'cd {new_path} && cd {parts[1]} && pwd'", tty=True)
        output = test.output.decode().strip()

        if output.startswith("/"):
            new_path = output  # valid new path
            print(new_path)
        else:
            print("Invalid path")

    else:
        cmd = f"bash -c 'cd {new_path} && {question}'"
        result = container.exec_run(cmd, tty=True)
        print(result.output.decode())
