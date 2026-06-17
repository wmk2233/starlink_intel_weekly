from __future__ import annotations

import argparse
import os
import socket
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_project_env() -> None:
    """Load local .env values when the file exists."""
    load_dotenv(PROJECT_ROOT / ".env")


def _split_recipients(value: str) -> list[str]:
    normalized = value.replace(";", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _get_config() -> tuple[dict[str, str], list[str]]:
    load_project_env()

    smtp_port = os.getenv("SMTP_PORT", "465").strip() or "465"
    mail_from = os.getenv("MAIL_FROM", "").strip() or os.getenv("SMTP_USER", "").strip()

    config = {
        "SMTP_HOST": os.getenv("SMTP_HOST", "").strip(),
        "SMTP_PORT": smtp_port,
        "SMTP_USER": os.getenv("SMTP_USER", "").strip(),
        "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD", "").strip(),
        "MAIL_TO": os.getenv("MAIL_TO", "").strip(),
        "MAIL_FROM": mail_from,
    }

    required = ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "MAIL_TO"]
    missing = [name for name in required if not config[name]]
    return config, missing


def build_message(
    markdown_path: Path,
    week_id: str,
    config: dict[str, str],
    collection_context: dict[str, str] | None = None,
) -> EmailMessage:
    markdown_text = markdown_path.read_text(encoding="utf-8")
    recipients = _split_recipients(config["MAIL_TO"])
    collection_context = collection_context or {}

    message = EmailMessage()
    message["Subject"] = f"Starlink 情报周报自动化测试 - {week_id}"
    message["From"] = config["MAIL_FROM"]
    message["To"] = ", ".join(recipients)

    body = (
        "本邮件由 starlink_intel_weekly 项目自动发送。\n"
        "当前阶段为阶段 2A：第一个真实来源接入测试。内容来自规则化网页采集，不包含大模型事实推理。\n\n"
        f"本次是否执行真实来源采集：{collection_context.get('collected', '未知')}\n"
        f"本次采集来源名称：{collection_context.get('source_names', '未知')}\n"
        f"本次采集条目数量：{collection_context.get('item_count', '未知')}\n\n"
        "以下为本次生成的 Markdown 正文：\n\n"
        f"{markdown_text}\n"
    )
    message.set_content(body)
    message.add_attachment(
        markdown_text.encode("utf-8"),
        maintype="text",
        subtype="markdown",
        filename=markdown_path.name,
    )
    return message


def send_weekly_email(
    markdown_path: str | Path,
    week_id: str,
    collection_context: dict[str, str] | None = None,
) -> bool:
    """Send the weekly Markdown as email body and attachment."""
    path = Path(markdown_path)
    config, missing = _get_config()

    if missing:
        print("邮件配置缺失，已取消发送。请先运行 python scripts/validate_env.py 检查配置。")
        print("缺失配置项：")
        for name in missing:
            print(f"- {name}")
        return False

    if not path.exists():
        print(f"邮件发送失败：附件路径不存在：{path}")
        return False

    recipients = _split_recipients(config["MAIL_TO"])
    if not recipients:
        print("邮件发送失败：MAIL_TO 未配置有效收件人。")
        return False

    try:
        port = int(config["SMTP_PORT"])
    except ValueError:
        print("邮件发送失败：SMTP_PORT 必须是数字。请先运行 python scripts/validate_env.py 检查配置。")
        return False

    message = build_message(path, week_id, config, collection_context=collection_context)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(config["SMTP_HOST"], port, context=context, timeout=30) as server:
            server.login(config["SMTP_USER"], config["SMTP_PASSWORD"])
            server.send_message(message)
        print(f"邮件发送成功：{', '.join(recipients)}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("邮件发送失败：SMTP 认证失败。")
        print("请检查 SMTP 授权码是否正确、邮箱 SMTP 服务是否开启、SMTP_USER 是否为正确发件账号。")
        return False
    except (socket.gaierror, TimeoutError, ConnectionRefusedError, smtplib.SMTPConnectError):
        print("邮件发送失败：无法连接 SMTP 服务器。")
        print("请检查网络连接、SMTP_HOST、SMTP_PORT，以及当前网络是否允许访问 SMTP 服务。")
        return False
    except smtplib.SMTPRecipientsRefused:
        print("邮件发送失败：收件人地址被 SMTP 服务器拒绝，请检查 MAIL_TO。")
        return False
    except smtplib.SMTPSenderRefused:
        print("邮件发送失败：发件人地址被 SMTP 服务器拒绝，请检查 MAIL_FROM 和 SMTP_USER。")
        return False
    except smtplib.SMTPException as exc:
        print(f"邮件发送失败：SMTP 服务返回错误：{exc.__class__.__name__}")
        print("请检查 SMTP 配置和邮箱服务状态。敏感信息未输出。")
        return False
    except OSError:
        print("邮件发送失败：网络或系统连接异常。")
        print("请检查网络、SMTP_HOST、SMTP_PORT 和本机代理/防火墙设置。")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="发送 Starlink 情报周报自动化测试邮件。")
    parser.add_argument("markdown_file", help="要发送的 Markdown 文件路径。")
    parser.add_argument("--week-id", help="周报编号，例如 2026-W25；默认使用文件名。")
    args = parser.parse_args()

    markdown_path = Path(args.markdown_file)
    week_id = args.week_id or markdown_path.stem
    return 0 if send_weekly_email(markdown_path, week_id) else 1


if __name__ == "__main__":
    sys.exit(main())
