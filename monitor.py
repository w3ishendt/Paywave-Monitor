from dataclasses import dataclass
from datetime import date, datetime, timedelta

from config_loader import load_config
from database import get_connection, get_table_name


@dataclass
class MonitorResult:
    status: str
    should_alert: bool
    reason: str
    expected_settlement_date: date
    latest_settlement_date: date | None
    total_rows: int
    expected_rows: int
    gap_days: int | None
    missing_daily_dates: list[date]
    missing_monthly_dates: list[date]


def normalize_date_value(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        return datetime.fromisoformat(value).date()

    raise TypeError(f"Unsupported date value type: {type(value)!r}")


def list_missing_dates(start_date, end_date, available_dates):
    if start_date > end_date:
        return []

    missing_dates = []
    current_date = start_date

    while current_date <= end_date:
        if current_date not in available_dates:
            missing_dates.append(current_date)
        current_date += timedelta(days=1)

    return missing_dates


def evaluate_paywave_health(as_of_date=None):
    config = load_config()
    monitor_config = config["monitor"]
    table_name = get_table_name()

    if as_of_date is None:
        as_of_date = date.today()

    expected_delay = monitor_config.get("expected_settlement_delay_days", 1)
    minimum_expected_rows = monitor_config.get("minimum_expected_rows", 1)
    allowed_lag_days = monitor_config.get("allowed_lag_days", expected_delay)
    recent_gap_check_days = monitor_config.get("recent_gap_check_days", 7)
    expected_settlement_date = as_of_date - timedelta(days=expected_delay)
    expected_settlement_date_value = expected_settlement_date.isoformat()
    recent_window_start = expected_settlement_date - timedelta(days=recent_gap_check_days - 1)
    month_window_start = expected_settlement_date.replace(day=1)

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            f"""
            SELECT
                COUNT(*) AS TotalRows,
                MAX(CAST(SettlementDate AS DATE)) AS LatestSettlementDate
            FROM {table_name}
            """
        )
        summary_row = cursor.fetchone()

        total_rows = int(summary_row[0] or 0)
        latest_settlement_date = normalize_date_value(summary_row[1])

        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM {table_name}
            WHERE CAST(SettlementDate AS DATE) = ?
            """,
            expected_settlement_date_value,
        )
        expected_rows = int(cursor.fetchone()[0] or 0)

        cursor.execute(
            f"""
            SELECT DISTINCT CAST(SettlementDate AS DATE)
            FROM {table_name}
            WHERE CAST(SettlementDate AS DATE) BETWEEN ? AND ?
            """,
            recent_window_start.isoformat(),
            expected_settlement_date_value,
        )
        available_recent_dates = {
            normalize_date_value(row[0])
            for row in cursor.fetchall()
            if row[0] is not None
        }

        cursor.execute(
            f"""
            SELECT DISTINCT CAST(SettlementDate AS DATE)
            FROM {table_name}
            WHERE CAST(SettlementDate AS DATE) BETWEEN ? AND ?
            """,
            month_window_start.isoformat(),
            expected_settlement_date_value,
        )
        available_monthly_dates = {
            normalize_date_value(row[0])
            for row in cursor.fetchall()
            if row[0] is not None
        }
    finally:
        conn.close()

    missing_daily_dates = list_missing_dates(
        recent_window_start,
        expected_settlement_date,
        available_recent_dates,
    )
    if available_monthly_dates:
        monthly_check_start = min(available_monthly_dates)
        missing_monthly_dates = list_missing_dates(
            monthly_check_start,
            expected_settlement_date,
            available_monthly_dates,
        )
    else:
        missing_monthly_dates = []

    if total_rows == 0 or latest_settlement_date is None:
        return MonitorResult(
            status="alert",
            should_alert=True,
            reason="no_paywave_data_received",
            expected_settlement_date=expected_settlement_date,
            latest_settlement_date=None,
            total_rows=total_rows,
            expected_rows=0,
            gap_days=None,
            missing_daily_dates=missing_daily_dates,
            missing_monthly_dates=missing_monthly_dates,
        )

    gap_days = (as_of_date - latest_settlement_date).days

    if expected_rows < minimum_expected_rows:
        return MonitorResult(
            status="alert",
            should_alert=True,
            reason="expected_report_empty_or_missing",
            expected_settlement_date=expected_settlement_date,
            latest_settlement_date=latest_settlement_date,
            total_rows=total_rows,
            expected_rows=expected_rows,
            gap_days=gap_days,
            missing_daily_dates=missing_daily_dates,
            missing_monthly_dates=missing_monthly_dates,
        )

    if missing_daily_dates:
        return MonitorResult(
            status="alert",
            should_alert=True,
            reason="missing_dates_within_recent_daily_window",
            expected_settlement_date=expected_settlement_date,
            latest_settlement_date=latest_settlement_date,
            total_rows=total_rows,
            expected_rows=expected_rows,
            gap_days=gap_days,
            missing_daily_dates=missing_daily_dates,
            missing_monthly_dates=missing_monthly_dates,
        )

    if missing_monthly_dates:
        return MonitorResult(
            status="alert",
            should_alert=True,
            reason="missing_dates_within_monthly_window",
            expected_settlement_date=expected_settlement_date,
            latest_settlement_date=latest_settlement_date,
            total_rows=total_rows,
            expected_rows=expected_rows,
            gap_days=gap_days,
            missing_daily_dates=missing_daily_dates,
            missing_monthly_dates=missing_monthly_dates,
        )

    if gap_days > allowed_lag_days:
        return MonitorResult(
            status="alert",
            should_alert=True,
            reason="settlement_data_stale",
            expected_settlement_date=expected_settlement_date,
            latest_settlement_date=latest_settlement_date,
            total_rows=total_rows,
            expected_rows=expected_rows,
            gap_days=gap_days,
            missing_daily_dates=missing_daily_dates,
            missing_monthly_dates=missing_monthly_dates,
        )

    return MonitorResult(
        status="healthy",
        should_alert=False,
        reason="healthy",
        expected_settlement_date=expected_settlement_date,
        latest_settlement_date=latest_settlement_date,
        total_rows=total_rows,
        expected_rows=expected_rows,
        gap_days=gap_days,
        missing_daily_dates=missing_daily_dates,
        missing_monthly_dates=missing_monthly_dates,
    )