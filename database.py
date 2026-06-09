import sqlite3
import pyodbc

from config_loader import load_config

def get_connection():
    config = load_config()
    database_config = config.get("database", {})
    engine = database_config.get("engine", "sql_server")

    if engine == "sqlite":
        sqlite_path = database_config.get("sqlite_path", "paywave_test.db")
        return sqlite3.connect(sqlite_path)

    sql_cfg = config["sql_server"]
    conn_str = (
        f"DRIVER={{SQL Server}};"
        f"SERVER={sql_cfg['server']};"
        f"DATABASE={sql_cfg['database']};"
        f"UID={sql_cfg['username']};"
        f"PWD={sql_cfg['password']};"
    )
    return pyodbc.connect(conn_str)


def get_table_name():
    config = load_config()
    database_config = config.get("database", {})
    return database_config.get("table_name", "dbo.tb_PWSettlement")