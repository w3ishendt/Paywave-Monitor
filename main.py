import argparse

from alert_state import (
    clear_alert_state,
    record_alert_sent,
    record_recovery_attempt,
    should_attempt_recovery,
    should_send_customer_alert,
    should_send_support_alert,
)
from auto_fix import AutoFixResult, build_auto_fix_plan, run_auto_fix
from auto_fix import write_failure_summary_log
from config_loader import load_config
from email_sender import send_email
from instance_lock import InstanceAlreadyRunningError, single_instance_lock
from monitor import evaluate_paywave_health


def format_date_list(values):
    if not values:
        return "None"

    return ", ".join(value.isoformat() for value in values)


def format_missing_dates_section(result):
    daily_dates = format_date_list(result.missing_daily_dates)
    monthly_dates = format_date_list(result.missing_monthly_dates)

    if result.missing_daily_dates == result.missing_monthly_dates:
        return (
            "Missing Settlement Dates (Daily/Monthly Check):\n"
            f"{daily_dates}"
        )

    return (
        "Missing Settlement Dates In Recent Daily Check:\n"
        f"{daily_dates}\n\n"
        "Missing Settlement Dates In Current Monthly Check:\n"
        f"{monthly_dates}"
    )

def format_auto_fix_section(auto_fix_result):
    if auto_fix_result is None or not auto_fix_result.enabled:
        return "Auto-Fix Attempt:\nNot enabled"

    plan = auto_fix_result.plan
    command_text = "Not available"
    if plan is not None:
        command_text = " ".join(plan.command)

    failure_period_text = "Not available"
    if auto_fix_result.failure_period_summary:
        failure_period_text = auto_fix_result.failure_period_summary

    return (
        "Auto-Fix Attempt:\n"
        f"{auto_fix_result.summary}\n\n"
        "Auto-Fix Command:\n"
        f"{command_text}\n\n"
        "ICPS Failure Periods From Logs:\n"
        f"{failure_period_text}"
    )


def build_support_body(site_name, result, auto_fix_result=None):
    return f"""
PayWave synchronization issue detected for {site_name}.

Alert reason:
{result.reason}

Expected Settlement Date:
{result.expected_settlement_date}

Latest Settlement Date In Database:
{result.latest_settlement_date}

Rows For Expected Settlement Date:
{result.expected_rows}

Total Rows In PayWave Table:
{result.total_rows}

{format_missing_dates_section(result)}

{format_auto_fix_section(auto_fix_result)}

Days Since Latest Settlement Date:
{result.gap_days if result.gap_days is not None else 'N/A'} day(s)

Investigation required.
""".strip()

def build_customer_body():
    return """
There is a delay in the report update.

Our team is monitoring the issue.

Please try generating the report again after 24 hours.
""".strip()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate the monitor without sending emails.",
    )
    args = parser.parse_args()

    config = load_config()
    monitor_config = config["monitor"]
    site_name = config["monitor"].get("site_name", "Unknown Site")
    alert_cooldown_hours = monitor_config.get("alert_cooldown_hours", 24)
    auto_fix_cooldown_hours = config.get("auto_fix", {}).get("attempt_cooldown_hours", 4)
    auto_fix_config = config.get("auto_fix", {})
    log_directory = auto_fix_config.get("log_directory")
    failure_summary_path = auto_fix_config.get("failure_summary_path", "logs/icps-failure-summary.log")

    if log_directory:
        summary_log_path = write_failure_summary_log(log_directory, failure_summary_path)
        print(f"ICPS failure summary log updated: {summary_log_path}")

    result = evaluate_paywave_health()

    if not result.should_alert:
        clear_alert_state(site_name)
        print(
            f"PayWave data healthy for {site_name}. "
            f"Expected settlement date {result.expected_settlement_date} has {result.expected_rows} row(s)."
        )
        return

    auto_fix_result = AutoFixResult(
        enabled=config.get("auto_fix", {}).get("enabled", False),
        attempted=False,
        succeeded=False,
        summary="Not attempted.",
    )

    auto_fix_plan_or_result = build_auto_fix_plan(config, result)

    if isinstance(auto_fix_plan_or_result, AutoFixResult):
        auto_fix_result = auto_fix_plan_or_result
    elif auto_fix_plan_or_result is not None:
        if args.dry_run:
            auto_fix_result = AutoFixResult(
                enabled=True,
                attempted=False,
                succeeded=False,
                summary=(
                    "Dry run only. Auto-fix was not executed, but it would run "
                    f"for --from {auto_fix_plan_or_result.from_date}."
                ),
                plan=auto_fix_plan_or_result,
            )
        else:
            should_attempt, recovery_signature = should_attempt_recovery(
                site_name,
                result,
                auto_fix_cooldown_hours,
            )
            if should_attempt:
                auto_fix_result = run_auto_fix(auto_fix_plan_or_result)
                record_recovery_attempt(site_name, recovery_signature, auto_fix_result.summary)
                result = evaluate_paywave_health()
                if not result.should_alert:
                    clear_alert_state(site_name)
                    print(
                        f"PayWave data recovered for {site_name}. "
                        f"{auto_fix_result.summary}"
                    )
                    return
            else:
                auto_fix_result = AutoFixResult(
                    enabled=True,
                    attempted=False,
                    succeeded=False,
                    summary=(
                        "Auto-fix skipped because the same recovery attempt was already made "
                        f"within the last {auto_fix_cooldown_hours} hour(s)."
                    ),
                    plan=auto_fix_plan_or_result,
                )

    support_body = build_support_body(site_name, result, auto_fix_result)
    customer_body = build_customer_body()

    if args.dry_run:
        print("Dry run only. Emails were not sent.")
        print()
        print("Support email preview:")
        print(support_body)
        print()
        if auto_fix_result.enabled:
            print("Auto-fix preview:")
            print(auto_fix_result.summary)
            print()
        print("Customer email preview:")
        print(customer_body)
        return

    should_send_support, support_signature = should_send_support_alert(
        site_name,
        result,
        alert_cooldown_hours,
    )
    should_send_customer, customer_signature = should_send_customer_alert(
        site_name,
        result,
    )

    if not should_send_support and not should_send_customer:
        print(
            f"Alerts suppressed for {site_name}. "
            f"Support is still within the {alert_cooldown_hours}-hour cooldown and customer was already notified for this unresolved issue."
        )
        return

    if should_send_support:
        send_email(
            config["email"]["support_recipients"],
            f"[ALERT] PayWave Missing Data - {site_name}",
            support_body,
        )
        record_alert_sent(site_name, "support", support_signature)

    if should_send_customer:
        send_email(
            config["email"]["customer_recipients"],
            f"PayWave Synchronization Delay - {site_name}",
            customer_body,
        )
        record_alert_sent(site_name, "customer", customer_signature)

    sent_channels = []
    if should_send_support:
        sent_channels.append("support")
    if should_send_customer:
        sent_channels.append("customer")

    print(f"Alert sent for {site_name}: {', '.join(sent_channels)}")

if __name__ == "__main__":
    try:
        with single_instance_lock("paywave-monitor.lock"):
            main()
    except InstanceAlreadyRunningError:
        print("Another PayWave monitor instance is already running. Exiting.")