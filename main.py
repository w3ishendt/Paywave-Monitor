import argparse

from alert_state import clear_alert_state, record_alert_sent, should_send_alert
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

def build_support_body(site_name, result):
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
    result = evaluate_paywave_health()

    if not result.should_alert:
        clear_alert_state(site_name)
        print(
            f"PayWave data healthy for {site_name}. "
            f"Expected settlement date {result.expected_settlement_date} has {result.expected_rows} row(s)."
        )
        return

    support_body = build_support_body(site_name, result)
    customer_body = build_customer_body()

    if args.dry_run:
        print("Dry run only. Emails were not sent.")
        print()
        print("Support email preview:")
        print(support_body)
        print()
        print("Customer email preview:")
        print(customer_body)
        return

    should_send, signature = should_send_alert(
        site_name,
        result,
        alert_cooldown_hours,
    )

    if not should_send:
        print(
            f"Alert suppressed for {site_name}. "
            f"The same issue was already sent within the last {alert_cooldown_hours} hour(s)."
        )
        return

    send_email(
        config["email"]["support_recipients"],
        f"[ALERT] PayWave Missing Data - {site_name}",
        support_body,
    )

    send_email(
        config["email"]["customer_recipients"],
        f"PayWave Synchronization Delay - {site_name}",
        customer_body,
    )

    record_alert_sent(site_name, signature)

    print(f"Alert sent for {site_name}")

if __name__ == "__main__":
    try:
        with single_instance_lock("paywave-monitor.lock"):
            main()
    except InstanceAlreadyRunningError:
        print("Another PayWave monitor instance is already running. Exiting.")