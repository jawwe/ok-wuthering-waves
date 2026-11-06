"""Distribution identity, independent of upstream's application/update channel."""
import os
from pathlib import Path

APP_NAME = "AsterDesk"
REPOSITORY = "jawwe/ok-wuthering-waves"
CHANNEL_BRANCH = "codex/independent-client"
RELEASE_PREFIX = "aster-v"
REPOSITORY_URL = f"https://github.com/{REPOSITORY}"
SOURCE_URL = f"{REPOSITORY_URL}/tree/{CHANNEL_BRANCH}"
APP_ROOT = Path(os.environ.get("ASTERDESK_ROOT", Path(__file__).resolve().parents[1]))
DATA_ROOT = APP_ROOT / "data"
CONFIG_ROOT = DATA_ROOT / "configs"
RESOURCE_ROOT = Path(__file__).resolve().parents[1] / "resources"


def distribution_version():
    import json
    try:
        return json.loads((APP_ROOT / "distribution.json").read_text(encoding="utf-8"))["version"]
    except (OSError, KeyError, ValueError, TypeError):
        return "dev"
