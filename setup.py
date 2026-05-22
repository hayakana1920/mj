import argparse
import base64
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PORTFOLIO_FILE = Path(__file__).parent / "portfolio.json"
FUND_NAMES = ["元本確保型", "国内債券", "国内株式", "外国債券", "外国株式"]


def load_or_init():
    if PORTFOLIO_FILE.exists():
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"allocations": {}, "target_allocations": {}, "history": []}


def save(data):
    data["last_updated"] = str(date.today())
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"portfolio.json を保存しました。")


def interactive_input(prompt_label):
    print(f"\n{prompt_label}を入力してください（合計が100%になるように）：")
    allocations = {}
    total = 0.0
    for fund in FUND_NAMES:
        while True:
            val = input(f"  {fund} [%]: ").strip()
            try:
                pct = float(val)
                if pct < 0 or pct > 100:
                    print("  0〜100の数値を入力してください。")
                    continue
                allocations[fund] = pct
                total += pct
                break
            except ValueError:
                print("  数値を入力してください（例: 23）。")
    print(f"\n合計: {total}%")
    if abs(total - 100) > 0.5:
        ans = input("合計が100%になっていません。続行しますか？ [y/N]: ").strip().lower()
        if ans != "y":
            sys.exit(0)
    return allocations


def read_from_image(image_path):
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[エラー] ANTHROPIC_API_KEY が設定されていません。.env を確認してください。")
        sys.exit(1)

    path = Path(image_path)
    if not path.exists():
        print(f"[エラー] ファイルが見つかりません: {image_path}")
        sys.exit(1)

    with open(path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    ext = path.suffix.lower().lstrip(".")
    media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/png")

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": image_data},
                },
                {
                    "type": "text",
                    "text": (
                        "この画像はDC（確定拠出年金）のポートフォリオ画面です。"
                        "各資産クラスの配分割合（%）をJSON形式のみで返してください。"
                        "使用するキーは「元本確保型」「国内債券」「国内株式」「外国債券」「外国株式」のみです。"
                        "例: {\"国内株式\": 23, \"外国株式\": 33, \"国内債券\": 20, \"外国債券\": 14, \"元本確保型\": 10}"
                        "JSONのみ返し、説明文は不要です。"
                    ),
                },
            ],
        }],
    )

    text = message.content[0].text.strip()
    match = re.search(r"\{[^}]+\}", text, re.DOTALL)
    if not match:
        print(f"[エラー] 画像からJSONを抽出できませんでした。レスポンス:\n{text}")
        sys.exit(1)
    try:
        return json.loads(match.group())
    except json.JSONDecodeError as e:
        print(f"[エラー] JSONの解析に失敗しました: {e}\n{match.group()}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="DC ポートフォリオ初期設定・更新")
    parser.add_argument("--interactive", action="store_true", help="対話形式で配分を入力")
    parser.add_argument("--update", action="store_true", help="目標配分を更新（省略時は現在配分を更新）")
    parser.add_argument("--image", metavar="ファイルパス", help="スクリーンショットから配分を読み取る")
    args = parser.parse_args()

    data = load_or_init()

    if args.image:
        print(f"画像からポートフォリオを読み取り中: {args.image}")
        allocations = read_from_image(args.image)
        print(f"読み取り結果: {allocations}")
        key = "target_allocations" if args.update else "allocations"
        data[key] = allocations
        save(data)

    elif args.interactive:
        label = "目標配分" if args.update else "現在の配分"
        allocations = interactive_input(label)
        key = "target_allocations" if args.update else "allocations"
        data[key] = allocations
        save(data)

    else:
        print("使い方:")
        print("  python setup.py --interactive                    # 現在の配分を対話入力")
        print("  python setup.py --update --interactive           # 目標配分を対話入力")
        print("  python setup.py --image screenshot.png           # 画像から現在の配分を読み取る")
        print("  python setup.py --update --image screenshot.png  # 画像から目標配分を読み取る")


if __name__ == "__main__":
    main()
