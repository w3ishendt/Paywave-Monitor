import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().with_name("config.json")

def load_config():
    with CONFIG_PATH.open(encoding="utf-8") as config_file:
        return json.load(config_file)