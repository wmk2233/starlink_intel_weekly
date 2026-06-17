from __future__ import annotations

import os
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


def main() -> int:
    print("开始检查环境变量配置。")

    if ENV_FILE.exists():
        print(".env: 已存在，将读取本地配置。")
        load_dotenv(ENV_FILE)
    else:
        print(".env: 未找到。这在当前阶段是正常情况，可使用 .env.example 创建本地配置。")

    missing: list[str] = []
    for name in REQUIRED_VARIABLES:
        value = os.getenv(name, "").strip()
        if value:
            if name in HIDDEN_VARIABLES:
                print(f"{name}: 已配置，但已隐藏")
            else:
                print(f"{name}: 已配置")
        else:
            print(f"{name}: 未配置")
            missing.append(name)

    if missing:
        print("\n以下配置项仍需补充：")
        for name in missing:
            print(f"- {name}")
        print("检查完成：存在缺失项。未打印任何密码、Token 或完整 Gitee Remote URL。")
    else:
        print("检查完成：所有配置项均已配置。敏感信息已隐藏。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
