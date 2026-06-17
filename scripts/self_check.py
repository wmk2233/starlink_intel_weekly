from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DIRECTORIES = [
    "scripts",
    "docs",
    "weekly",
    ".github/workflows",
    "outputs/logs",
]


def _run_git_check_ignore(path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", path],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def main() -> int:
    print("开始执行项目自检。")
    failed = False

    version = sys.version_info
    print(f"Python 版本：{version.major}.{version.minor}.{version.micro}")
    if (version.major, version.minor) < (3, 11):
        print("Python 版本检查：未通过，需要 Python 3.11 或以上版本。")
        failed = True
    else:
        print("Python 版本检查：通过。")

    for directory in REQUIRED_DIRECTORIES:
        path = PROJECT_ROOT / directory
        if path.is_dir():
            print(f"目录检查：{directory} 已存在")
        else:
            print(f"目录检查：{directory} 不存在")
            failed = True

    if _run_git_check_ignore(".env"):
        print(".env 忽略检查：通过")
    else:
        print(".env 忽略检查：未通过，请检查 .gitignore")
        failed = True

    if _run_git_check_ignore("prompts/"):
        print("prompts/ 忽略检查：通过")
    else:
        print("prompts/ 忽略检查：未通过，请检查 .gitignore")
        failed = True

    print("环境变量格式检查请运行：python scripts/validate_env.py")
    print("自检未读取、未打印 .env 内容。")

    if failed:
        print("自检完成：存在需要处理的问题。")
        return 1

    print("自检完成：基础工程状态正常。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
