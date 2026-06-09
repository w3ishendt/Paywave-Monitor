import sqlite3
from datetime import date, timedelta

from config_loader import load_config


def main():
    config = load_config()
    database_config = config.get("database", {})
    sqlite_path = database_config.get("sqlite_path", "paywave_test.db")
    table_name = database_config.get("table_name", "tb_PWSettlement")

    connection = sqlite3.connect(sqlite_path)

    try:
        cursor = connection.cursor()
        cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        cursor.execute(
            f'''
            CREATE TABLE "{table_name}" (
                ID INTEGER PRIMARY KEY,
                TransactionID TEXT,
                MerchantID TEXT,
                TerminalID TEXT,
                EntryDateTime TEXT,
                PaymentDateTime TEXT,
                ParkingDuration TEXT,
                TrxnAmt REAL,
                EntryCard TEXT,
                PaymentCard TEXT,
                ApprovalCode TEXT,
                IsSettled INTEGER,
                SettlementDate TEXT
            )
            '''
        )

        today = date.today()
        rows = [
            (
                1,
                "TXN-20260605-001",
                "04800002383842",
                "91101499",
                "2026-06-05 08:05:00",
                "2026-06-05 10:11:00",
                "2 Hours 6 Minutes",
                3.00,
                "5491860105",
                "5491860105",
                "223862",
                1,
                str(today - timedelta(days=3)),
            ),
            (
                2,
                "TXN-20260606-001",
                "04800002383842",
                "91101500",
                "2026-06-06 09:17:00",
                "2026-06-06 11:49:00",
                "2 Hours 32 Minutes",
                2.00,
                "4283329258",
                "4283329258",
                "550150",
                1,
                str(today - timedelta(days=2)),
            ),
        ]

        cursor.executemany(
            f'''
            INSERT INTO "{table_name}" (
                ID,
                TransactionID,
                MerchantID,
                TerminalID,
                EntryDateTime,
                PaymentDateTime,
                ParkingDuration,
                TrxnAmt,
                EntryCard,
                PaymentCard,
                ApprovalCode,
                IsSettled,
                SettlementDate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            rows,
        )
        connection.commit()
    finally:
        connection.close()

    print(f"Seeded local SQLite test database at {sqlite_path} with intentional missing data.")
    print(f"Missing settlement date for alert testing: {today - timedelta(days=1)}")


if __name__ == "__main__":
    main()