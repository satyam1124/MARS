"""Developer tools skills for MARS."""

import os
import subprocess
from pathlib import Path


def _run(cmd: list[str], cwd: str | None = None, timeout: int = 30) -> tuple[str, str, int]:
    """Run a subprocess and return (stdout, stderr, returncode)."""
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def run_terminal_command(command: str, confirmed: bool = False) -> str:
    """Execute an arbitrary shell command.

    ⚠️  This is potentially dangerous. Requires confirmed=True.

    Args:
        command: Shell command to execute.
        confirmed: Must be True to actually run the command.

    Returns:
        Command output or error message.
    """
    if not confirmed:
        return (
            f"About to run shell command: '{command}'\n"
            "This can be dangerous. Call run_terminal_command again with confirmed=True to proceed."
        )
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=60
        )
        output = result.stdout.strip()
        err = result.stderr.strip()
        if result.returncode != 0:
            return f"Command exited with code {result.returncode}.\n{err or output}"
        return output or "Command completed with no output."
    except subprocess.TimeoutExpired:
        return "Command timed out after 60 seconds."
    except Exception as e:
        return f"Failed to run command: {e}"


def run_python_script(path: str) -> str:
    """Execute a Python script file.

    Args:
        path: Path to the Python script.

    Returns:
        Script output or error message.
    """
    script_path = str(Path(path).expanduser().resolve())
    if not Path(script_path).exists():
        return f"Script not found: {script_path}"
    try:
        stdout, stderr, code = _run(["python3", script_path], timeout=60)
        if code != 0:
            return f"Script exited with code {code}.\n{stderr or stdout}"
        return stdout or "Script completed with no output."
    except subprocess.TimeoutExpired:
        return "Script timed out after 60 seconds."
    except Exception as e:
        return f"Failed to run script: {e}"


def git_status(repo_path: str = ".") -> str:
    """Show the git status of a repository.

    Args:
        repo_path: Path to the git repository (default: current directory).

    Returns:
        Git status output as a string.
    """
    cwd = str(Path(repo_path).expanduser().resolve())
    try:
        stdout, stderr, code = _run(["git", "status", "--short", "--branch"], cwd=cwd)
        if code != 0:
            return f"Git status failed: {stderr}"
        return stdout or "Nothing to report — working tree is clean."
    except Exception as e:
        return f"Git status error: {e}"


def git_commit(message: str, repo_path: str = ".") -> str:
    """Stage all changes and create a git commit.

    Args:
        message: Commit message.
        repo_path: Path to the git repository (default: current directory).

    Returns:
        Commit result as a string.
    """
    cwd = str(Path(repo_path).expanduser().resolve())
    try:
        # Stage all
        stdout, stderr, code = _run(["git", "add", "-A"], cwd=cwd)
        if code != 0:
            return f"git add failed: {stderr}"
        stdout, stderr, code = _run(["git", "commit", "-m", message], cwd=cwd)
        if code != 0:
            return f"git commit failed: {stderr}"
        return stdout or "Commit created."
    except Exception as e:
        return f"Git commit error: {e}"


def git_pull(repo_path: str = ".") -> str:
    """Pull the latest changes from the remote repository.

    Args:
        repo_path: Path to the git repository (default: current directory).

    Returns:
        Pull result as a string.
    """
    cwd = str(Path(repo_path).expanduser().resolve())
    try:
        stdout, stderr, code = _run(["git", "pull"], cwd=cwd, timeout=60)
        if code != 0:
            return f"git pull failed: {stderr}"
        return stdout or "Already up to date."
    except Exception as e:
        return f"Git pull error: {e}"


def open_vscode(path: str = ".") -> str:
    """Open a file or directory in Visual Studio Code.

    Args:
        path: Path to the file or directory to open.

    Returns:
        Confirmation or error message.
    """
    target = str(Path(path).expanduser().resolve())
    try:
        subprocess.Popen(["code", target])
        return f"Opening '{target}' in VS Code."
    except FileNotFoundError:
        return "VS Code CLI ('code') not found. Make sure it's installed and in your PATH."
    except Exception as e:
        return f"Failed to open VS Code: {e}"


def docker_ps() -> str:
    """List running Docker containers.

    Returns:
        List of running containers as a string.
    """
    try:
        stdout, stderr, code = _run(
            ["docker", "ps", "--format", "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"]
        )
        if code != 0:
            return f"docker ps failed: {stderr}"
        return stdout or "No running containers."
    except FileNotFoundError:
        return "Docker is not installed or not in PATH."
    except Exception as e:
        return f"docker ps error: {e}"


def docker_start(container: str) -> str:
    """Start a Docker container.

    Args:
        container: Container name or ID.

    Returns:
        Result as a string.
    """
    try:
        stdout, stderr, code = _run(["docker", "start", container])
        if code != 0:
            return f"docker start failed: {stderr}"
        return f"Started container '{container}'."
    except FileNotFoundError:
        return "Docker is not installed or not in PATH."
    except Exception as e:
        return f"docker start error: {e}"


def docker_stop(container: str, confirmed: bool = False) -> str:
    """Stop a running Docker container.

    Args:
        container: Container name or ID.
        confirmed: Must be True to actually stop the container.

    Returns:
        Result as a string.
    """
    if not confirmed:
        return (
            f"About to stop container '{container}'. "
            "Call docker_stop again with confirmed=True to proceed."
        )
    try:
        stdout, stderr, code = _run(["docker", "stop", container])
        if code != 0:
            return f"docker stop failed: {stderr}"
        return f"Stopped container '{container}'."
    except FileNotFoundError:
        return "Docker is not installed or not in PATH."
    except Exception as e:
        return f"docker stop error: {e}"


def ssh_connect(host: str, username: str, port: int = 22) -> str:
    """Open an SSH connection in a new Terminal window.

    Args:
        host: Hostname or IP address.
        username: SSH username.
        port: SSH port (default: 22).

    Returns:
        Confirmation or error message.
    """
    ssh_cmd = f"ssh -p {port} {username}@{host}"
    try:
        # macOS: open a new Terminal window
        apple_script = f'tell application "Terminal" to do script "{ssh_cmd}"'
        subprocess.Popen(["osascript", "-e", apple_script])
        return f"Opening SSH connection to {username}@{host}:{port} in Terminal."
    except FileNotFoundError:
        try:
            # Linux: try xterm
            subprocess.Popen(["xterm", "-e", ssh_cmd])
            return f"Opening SSH connection to {username}@{host}:{port}."
        except Exception as e:
            return f"Failed to open terminal for SSH: {e}"
    except Exception as e:
        return f"Failed to launch SSH: {e}"


def ping_host(host: str) -> str:
    """Ping a host and return the result.

    Args:
        host: Hostname or IP address to ping.

    Returns:
        Ping result as a string.
    """
    try:
        stdout, stderr, code = _run(["ping", "-c", "4", host], timeout=15)
        if code != 0:
            return f"Ping to '{host}' failed. Host may be unreachable.\n{stderr}"
        # Extract summary line
        lines = stdout.splitlines()
        summary = [l for l in lines if "packet" in l or "min/avg" in l]
        return "\n".join(summary) if summary else stdout
    except subprocess.TimeoutExpired:
        return f"Ping to '{host}' timed out."
    except Exception as e:
        return f"Ping error: {e}"
