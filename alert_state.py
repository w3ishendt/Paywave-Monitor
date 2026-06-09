import json
from datetime import datetime, timedelta
from pathlib import Path


STATE_DIR = Path(__file__).resolve().with_name("logs")
STATE_PATH = STATE_DIR / "alert-state.json"


def _ensure_state_dir():
    STATE_DIR.mkdir(exist_ok=True)


def _load_state():
    if not STATE_PATH.exists():
        return {}

    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state):
    _ensure_state_dir()
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def build_alert_signature(result):
    return json.dumps(
        {
            "reason": result.reason,
            "expected_settlement_date": result.expected_settlement_date.isoformat(),
            "latest_settlement_date": (
                result.latest_settlement_date.isoformat()
                if result.latest_settlement_date is not None
                else None
            ),
            "expected_rows": result.expected_rows,
            "missing_daily_dates": [value.isoformat() for value in result.missing_daily_dates],
            "missing_monthly_dates": [value.isoformat() for value in result.missing_monthly_dates],
        },
        sort_keys=True,
    )


def should_send_alert(site_name, result, cooldown_hours):
    state = _load_state()
    site_state = state.get(site_name)
    signature = build_alert_signature(result)

    if not site_state:
        return True, signature

    if site_state.get("signature") != signature:
        return True, signature

    last_sent_at_raw = site_state.get("last_sent_at")
    if not last_sent_at_raw:
        return True, signature

    last_sent_at = datetime.fromisoformat(last_sent_at_raw)
    cooldown_until = last_sent_at + timedelta(hours=cooldown_hours)

    return datetime.now() >= cooldown_until, signature


def record_alert_sent(site_name, signature):
    state = _load_state()
    state[site_name] = {
        "signature": signature,
        "last_sent_at": datetime.now().isoformat(timespec="seconds"),
    }
    _save_state(state)


def clear_alert_state(site_name):
    state = _load_state()
    if site_name not in state:
        return

    del state[site_name]
    _save_state(state)