import argparse
import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

from analyzer import analyze

load_dotenv()

LOG_DIR = Path(__file__).parent / "logs"


def send_email(subject, body):
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD")
    notify_email = os.environ.get("NOTIFY_EMAIL")

    if not all([gmail_user, gmail_pass, notify_email]):
        raise ValueError(
            "メール設定が不完全です。.env を確認してください（GMAIL_USER / GMAIL_APP_PASSWORD / NOTIFY_EMAIL）"
        )

    msg = MIMEMultipart()
    msg["From"] = gmail_user
    msg["To"] = notify_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.send_message(msg)
    except smtplib.SMTPException as e:
        raise RuntimeError(f"メール送信に失敗しました: {e}")


def run(dry_run=False):
    LOG_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    try:
        analysis = analyze(dry_run=dry_run)
    except Exception as e:
        print(f"[エラー] 分析に失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    subject = f"DC運用レポート {timestamp}"
    body = f"{analysis}\n\n-- 自動送信 {timestamp}"

    if dry_run:
        print("=== DRY RUN モード（メール送信なし）===")
        print(f"件名: {subject}")
        print(f"本文:\n{body}")
        return

    try:
        send_email(subject, body)
        print(f"レポートを送信しました: {timestamp}")
    except (ValueError, RuntimeError) as e:
        print(f"[エラー] {e}", file=sys.stderr)
        sys.exit(1)

    log_file = LOG_DIR / f"{datetime.now().strftime('%Y%m%d')}.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] 送信完了\n{analysis}\n\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DC ポートフォリオ週次モニター")
    parser.add_argument("--dry-run", action="store_true", help="メール送信せずに結果を表示")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
