from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import subprocess


@dataclass
class AutoFixPlan:
    executable_path: Path
    working_directory: Path
    log_directory: Path
    failure_summary_path: Path
    from_date: str
    timeout_seconds: int

    @property
    def command(self):
        return [str(self.executable_path), "--from", self.from_date]


@dataclass
class AutoFixResult:
    enabled: bool
    attempted: bool
    succeeded: bool
    summary: str
    plan: AutoFixPlan | None = None
    failure_period_summary: str | None = None


RUN_TIMESTAMP_PATTERN = re.compile(r"^(?:INFO|DEBUG|ERROR):\s+(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})")


@dataclass
class LogRunSummary:
    started_at: datetime | None = None
    ended_at: datetime | None = None
    failed: bool = False
    failure_messages: list[str] | None = None

    def __post_init__(self):
        if self.failure_messages is None:
            self.failure_messages = []


def parse_log_timestamp(line):
    match = RUN_TIMESTAMP_PATTERN.match(line)
    if not match:
        return None

    return datetime.strptime(match.group(1), "%Y/%m/%d %H:%M:%S")


def extract_failure_period_summary(log_directory, max_failures=5):
    log_directory = Path(log_directory)

    if not log_directory.exists():
        return "ICPS log directory not found."

    runs = []
    current_run = None

    for log_path in sorted(log_directory.glob("settlement_sync_*.log")):
        with log_path.open(encoding="utf-8", errors="replace") as log_file:
            for raw_line in log_file:
                line = raw_line.strip()
                timestamp = parse_log_timestamp(line)

                if "Logger initialized successfully" in line:
                    if current_run is not None:
                        runs.append(current_run)
                    current_run = LogRunSummary(started_at=timestamp)
                    continue

                if current_run is None:
                    continue

                if timestamp is not None:
                    current_run.ended_at = timestamp

                if line.startswith("ERROR:"):
                    current_run.failed = True
                    current_run.failure_messages.append(line)
                    continue

                if "Settlement sync process completed successfully" in line:
                    runs.append(current_run)
                    current_run = None

    if current_run is not None:
        runs.append(current_run)

    failed_runs = [run for run in runs if run.failed]
    if not failed_runs:
        return "No failed ICPS runs found in the log directory."

    summaries = []
    for run in failed_runs[-max_failures:]:
        start_text = run.started_at.strftime("%Y-%m-%d %H:%M:%S") if run.started_at else "Unknown"
        end_text = run.ended_at.strftime("%Y-%m-%d %H:%M:%S") if run.ended_at else start_text
        reason_text = run.failure_messages[-1] if run.failure_messages else "Unknown failure"
        summaries.append(f"{start_text} to {end_text} | {reason_text}")

    return "\n".join(summaries)


def build_failure_summary_report(log_directory, max_failures=20):
    log_directory = Path(log_directory)

    if not log_directory.exists():
        return "ICPS Failure Summary\n====================\nSource log directory not found."

    runs = []
    current_run = None

    for log_path in sorted(log_directory.glob("settlement_sync_*.log")):
        with log_path.open(encoding="utf-8", errors="replace") as log_file:
            for raw_line in log_file:
                line = raw_line.strip()
                timestamp = parse_log_timestamp(line)

                if "Logger initialized successfully" in line:
                    if current_run is not None:
                        runs.append(current_run)
                    current_run = LogRunSummary(started_at=timestamp)
                    continue

                if current_run is None:
                    continue

                if timestamp is not None:
                    current_run.ended_at = timestamp

                if line.startswith("ERROR:"):
                    current_run.failed = True
                    current_run.failure_messages.append(line)
                    continue

                if "Settlement sync process completed successfully" in line:
                    runs.append(current_run)
                    current_run = None

    if current_run is not None:
        runs.append(current_run)

    failed_runs = [run for run in runs if run.failed]
    header = [
        "ICPS Failure Summary",
        "====================",
        f"Source Log Directory: {log_directory}",
        f"Generated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    if not failed_runs:
        header.append("No failed ICPS runs found.")
        return "\n".join(header)

    header.append(f"Recent Failed Runs: {min(len(failed_runs), max_failures)} of {len(failed_runs)}")
    header.append("")

    entries = []
    for index, run in enumerate(failed_runs[-max_failures:], start=1):
        start_text = run.started_at.strftime("%Y-%m-%d %H:%M:%S") if run.started_at else "Unknown"
        end_text = run.ended_at.strftime("%Y-%m-%d %H:%M:%S") if run.ended_at else start_text
        reason_text = run.failure_messages[-1] if run.failure_messages else "Unknown failure"
        entries.extend(
            [
                f"{index}. Failed Period: {start_text} to {end_text}",
                f"   Reason: {reason_text}",
                "",
            ]
        )

    return "\n".join(header + entries).rstrip()


def write_failure_summary_log(log_directory, output_path, max_failures=20):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = build_failure_summary_report(log_directory, max_failures=max_failures)
    output_path.write_text(report + "\n", encoding="utf-8")
    return output_path


def determine_from_date(result):
    if result.missing_monthly_dates:
        return min(result.missing_monthly_dates).isoformat()

    if result.missing_daily_dates:
        return min(result.missing_daily_dates).isoformat()

    return result.expected_settlement_date.isoformat()


def build_auto_fix_plan(config, result):
    auto_fix_config = config.get("auto_fix", {})
    if not auto_fix_config.get("enabled", False):
        return None

    executable_value = auto_fix_config.get("executable_path")
    if not executable_value:
        return AutoFixResult(
            enabled=True,
            attempted=False,
            succeeded=False,
            summary="Auto-fix is enabled but no executable_path is configured.",
        )

    executable_path = Path(executable_value)
    working_directory = executable_path.parent
    log_directory_value = auto_fix_config.get("log_directory", str(working_directory / "logs"))
    log_directory = Path(log_directory_value)
    failure_summary_path_value = auto_fix_config.get(
        "failure_summary_path",
        str(Path("logs") / "icps-failure-summary.log"),
    )
    failure_summary_path = Path(failure_summary_path_value)
    timeout_seconds = int(auto_fix_config.get("attempt_timeout_seconds", 1800))
    from_date = determine_from_date(result)

    plan = AutoFixPlan(
        executable_path=executable_path,
        working_directory=working_directory,
        log_directory=log_directory,
        failure_summary_path=failure_summary_path,
        from_date=from_date,
        timeout_seconds=timeout_seconds,
    )

    return plan


def run_auto_fix(plan):
    if not plan.executable_path.exists():
        return AutoFixResult(
            enabled=True,
            attempted=False,
            succeeded=False,
            summary=f"Auto-fix executable not found at {plan.executable_path}.",
            plan=plan,
            failure_period_summary=extract_failure_period_summary(plan.log_directory),
        )

    try:
        completed = subprocess.run(
            plan.command,
            cwd=plan.working_directory,
            capture_output=True,
            text=True,
            timeout=plan.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return AutoFixResult(
            enabled=True,
            attempted=True,
            succeeded=False,
            summary=(
                "Auto-fix command timed out after "
                f"{plan.timeout_seconds} second(s)."
            ),
            plan=plan,
            failure_period_summary=extract_failure_period_summary(plan.log_directory),
        )
    except OSError as exc:
        return AutoFixResult(
            enabled=True,
            attempted=True,
            succeeded=False,
            summary=f"Auto-fix command failed to start: {exc}",
            plan=plan,
            failure_period_summary=extract_failure_period_summary(plan.log_directory),
        )

    if completed.returncode == 0:
        return AutoFixResult(
            enabled=True,
            attempted=True,
            succeeded=True,
            summary=(
                "Auto-fix command completed successfully "
                f"for --from {plan.from_date}."
            ),
            plan=plan,
            failure_period_summary=extract_failure_period_summary(plan.log_directory),
        )

    stderr_output = (completed.stderr or "").strip()
    stdout_output = (completed.stdout or "").strip()
    detail = stderr_output or stdout_output or "No output captured."

    return AutoFixResult(
        enabled=True,
        attempted=True,
        succeeded=False,
        summary=(
            f"Auto-fix command exited with code {completed.returncode}. "
            f"Output: {detail}"
        ),
        plan=plan,
        failure_period_summary=extract_failure_period_summary(plan.log_directory),
    )