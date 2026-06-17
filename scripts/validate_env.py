from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
REQUIRED_VARIABLES = [
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "MAIL_TO",
    "MAIL_FROM",
    "GITEE_REMOTE",
]
HIDDEN_VARIABLES = {"SMTP_PASSWORD", "GITEE_REMOTE"}
EMAIL_PATTERN = re.compile(r"^[^@\s=]+@[^@\s=]+\.[^@\s=]+$")
NO_LEADING_EQUALS_VARIABLES = {"SMTP_HOST", "SMTP_USER", "MAIL_FROM", "MAIL_TO"}


def _status_text(name: str, value: str) -> str:
    if not value:
        return f"{name}: 未配置"
    if name in HIDDEN_VARIABLES:
        return f"{name}: 已配置，但已隐藏"
    return f"{name}: 已配置"


def _validate_no_leading_equals(name: str, value: str, errors: list[str]) -> None:
    if name in NO_LEADING_EQUALS_VARIABLES and value.startswith("="):
        errors.append(f"{name}: 检测到配置值前存在多余的等号，请检查 .env 写法")


def _validate_email(name: str, value: str, errors: list[str]) -> None:
    if value and not EMAIL_PATTERN.match(value):
        errors.append(f"{name}: 邮箱格式不正确，请检查配置")


def _validate_port(value: str, errors: list[str]) -> None:
    try:
        port = int(value)
    except ValueError:
        errors.append("SMTP_PORT: 必须是 1 到 65535 之间的整数")
        return

    if port < 1 or port > 65535:
        errors.append("SMTP_PORT: 必须是 1 到 65535 之间的整数")


def main() -> int:
    print("开始检查环境变量配置。")

    if ENV_FILE.exists():
        print(".env: 已存在，将读取本地配置。")
        load_dotenv(ENV_FILE)
    else:
        print(".env: 未找到。这在当前阶段是正常情况，可使用 .env.example 创建本地配置。")

    values = {name: os.getenv(name, "").strip() for name in REQUIRED_VARIABLES}
    missing: list[str] = []
    errors: list[str] = []

    for name in REQUIRED_VARIABLES:
        value = values[name]
        print(_status_text(name, value))
        if not value:
            missing.append(name)
            continue
        _validate_no_leading_equals(name, value, errors)

    if values["SMTP_HOST"] and not values["SMTP_HOST"].startswith("="):
        if any(char.isspace() for char in values["SMTP_HOST"]):
            errors.append("SMTP_HOST: 不应包含空白字符")

    if values["SMTP_PORT"]:
        _validate_port(values["SMTP_PORT"], errors)

    _validate_email("SMTP_USER", values["SMTP_USER"], errors)
    _validate_email("MAIL_FROM", values["MAIL_FROM"], errors)
    _validate_email("MAIL_TO", values["MAIL_TO"], errors)

    if values["MAIL_TO"] and ("," in values["MAIL_TO"] or ";" in values["MAIL_TO"]):
        errors.append("MAIL_TO: 当前脚本要求配置单个收件邮箱，请不要使用逗号或分号分隔")

    if values["GITEE_REMOTE"]:
        if not (values["GITEE_REMOTE"].startswith("https://") or values["GITEE_REMOTE"].startswith("git@")):
            errors.append("GITEE_REMOTE: 如果配置，应当以 https:// 或 git@ 开头")

    if missing:
        print("\n以下配置项仍需补充：")
        for name in missing:
            print(f"- {name}")

    if errors:
        print("\n以下配置项存在格式问题：")
        for error in errors:
            print(f"- {error}")

    if missing or errors:
        print("\n检查完成：存在缺失项或格式错误。未打印任何密码、Token 或完整 Gitee Remote URL。")
        return 1

    print("\n检查完成：所有配置项均已配置，格式检查通过。敏感信息已隐藏。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
