import docker

class DockerShell:
    def __init__(self, container_name="my_ubuntu_container", image="ubuntu", workdir="/opt"):
        self.client = docker.from_env()
        self.container_name = container_name
        self.image = image
        self.workdir = workdir
        self.current_path = workdir
        self.container = self._get_or_start_container()

    def _get_or_start_container(self):
        try:
            container = self.client.containers.get(self.container_name)
            if container.status != "running":
                print(f"Starting container '{self.container_name}'...")
                container.start()
        except docker.errors.NotFound:
            print(f"Creating new container '{self.container_name}'...")
            container = self.client.containers.run(
                self.image,
                command="bash",
                tty=True,
                stdin_open=True,
                working_dir=self.workdir,
                detach=True,
                name=self.container_name
            )
        return self.client.containers.get(self.container_name)  # Ensure fresh reference

    def run_command(self, command: str) -> str:
        if command.strip() in ["exit", "quit"]:
            return "Exiting..."

        # Handle 'cd' separately to change context
        if command.strip().startswith("cd "):
            target = command.strip().split("cd", 1)[1].strip()
            check_path_cmd = f"bash -c 'cd \"{self.current_path}\" && cd \"{target}\" && pwd'"
            result = self.container.exec_run(check_path_cmd, tty=True)
            output = result.output.decode().strip()
            if result.exit_code == 0:
                self.current_path = output
                return f"Changed directory to {self.current_path}"
            else:
                return "❌ Invalid directory."

        # For all other commands, run them in the current path
        full_cmd = f"bash -c 'cd \"{self.current_path}\" && {command}'"
        result = self.container.exec_run(full_cmd, tty=True)
        return result.output.decode(errors="ignore").strip()

    def get_current_path(self):
        return self.current_path
