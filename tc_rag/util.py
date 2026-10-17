from __future__ import annotations

import hashlib, json, os, re
from pathlib import Path
from typing import Any

FORMULA_PREFIXES = ("=", "+", "-", "@")


def load_dotenv(path: Path = Path(".env")) -> bool:
    """Load simple KEY=VALUE pairs without overriding the process environment."""
    if not path.is_file():
        return False
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"invalid .env line {number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"invalid .env key on line {number}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)
    return True


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).replace("\r\n", "\n").replace("\r", "\n").strip()


def canonical(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", value.casefold())


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def safe_cell(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.lstrip()
    return "'" + value if stripped.startswith(FORMULA_PREFIXES) else value


def split_numbered(text: str) -> tuple[str, list[str]]:
    text = clean_text(text)
    if not text:
        return "", []
    lines = text.splitlines()
    steps, prefix = [], []
    current = ""
    found = False
    for line in lines:
        m = re.match(r"^\s*(\d+)[.)]\s*(.*)$", line)
        if m:
            if current:
                steps.append(current.strip())
            current, found = m.group(2), True
        elif found:
            current += ("\n" if current else "") + line
        else:
            prefix.append(line)
    if current:
        steps.append(current.strip())
    return "\n".join(prefix).strip(), steps


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)



