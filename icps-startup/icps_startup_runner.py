import json
import subprocess

from datetime import date
from pathlib import Path

from instance_lock import InstanceAlreadyRunningError, single_instance_lock


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "icps_startup_config.json"


def load_config():
    with CONFIG_PATH.open(encoding="utf-8") as config_file:
        return json.load(config_file)


def resolve_from_date(config):
    mode = config.get("from_date_mode", "start_of_month")
    if mode == "fixed":
        fixed_from_date = config.get("fixed_from_date")
        if not fixed_from_date:
            raise ValueError(
                "fixed_from_date is required when from_date_mode is set to 'fixed'."
            )
        return fixed_from_date

    if mode == "today":
        return date.today().isoformat()

    today = date.today()
    return today.replace(day=1).isoformat()


def write_log(log_path, lines):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write("\n".join(lines))
        log_file.write("\n\n")


def main():
    config = load_config()

    executable_path = Path(config.get("executable_path", ".\\icps-ftp.exe"))
    if not executable_path.is_absolute():
        executable_path = (SCRIPT_DIR / executable_path).resolve()

    working_directory = Path(config.get("working_directory", str(executable_path.parent)))
    if not working_directory.is_absolute():
        working_directory = (SCRIPT_DIR / working_directory).resolve()

    log_path = Path(config.get("log_path", ".\\logs\\icps-startup-runner.log"))
    if not log_path.is_absolute():
        log_path = (SCRIPT_DIR / log_path).resolve()

    from_date = resolve_from_date(config)
    command = [str(executable_path), "--from", from_date]

    if not executable_path.exists():
        write_log(
            log_path,
            [
                f"[{date.today().isoformat()}]",
                f"Executable not found: {executable_path}",
            ],
        )
        raise FileNotFoundError(f"ICPS executable not found: {executable_path}")

    completed = subprocess.run(
        command,
        cwd=working_directory,
        capture_output=True,
        text=True,
        check=False,
    )

    log_lines = [
        f"[{date.today().isoformat()}]",
        f"Working directory: {working_directory}",
        f"Command: {' '.join(command)}",
        f"Exit code: {completed.returncode}",
    ]

    stdout_output = (completed.stdout or "").strip()
    stderr_output = (completed.stderr or "").strip()

    if stdout_output:
        log_lines.append("Stdout:")
        log_lines.append(stdout_output)

    if stderr_output:
        log_lines.append("Stderr:")
        log_lines.append(stderr_output)

    write_log(log_path, log_lines)

    if completed.returncode != 0:
        raise RuntimeError(
            f"ICPS startup runner failed with exit code {completed.returncode}."
        )


if __name__ == "__main__":
    try:
        with single_instance_lock("icps-startup-runner.lock"):
            main()
    except InstanceAlreadyRunningError:
        print("Another ICPS startup runner instance is already running. Exiting.")