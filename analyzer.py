import json
from pathlib import Path

from dotenv import load_dotenv

from market_data import get_market_data
from simulate import simulate_two_phase, expected_return, TARGET, GOOD_BOOST, BAD_DRAG

load_dotenv()

PORTFOLIO_FILE = Path(__file__).parent / "portfolio.json"
REBALANCE_THRESHOLD = 5.0


def load_portfolio():
    if not PORTFOLIO_FILE.exists():
        raise FileNotFoundError("portfolio.json が見つかりません。setup.py を実行してください。")
    with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"portfolio.json の解析に失敗しました: {e}")


def _category_totals(funds):
    totals = {}
    for f in funds:
        cat = f["category"]
        totals[cat] = totals.get(cat, 0) + f["allocation"]
    return totals


def _funds_in_category(funds, category):
    return [f for f in funds if f["category"] == category]


def _proportional_changes(funds_in_cat, total_change):
    cat_total = sum(f["allocation"] for f in funds_in_cat)
    result = []
    for f in funds_in_cat:
        ratio = f["allocation"] / cat_total if cat_total > 0 else 1 / len(funds_in_cat)
        change = round(total_change * ratio, 1)
        new_alloc = round(f["allocation"] + change, 1)
        result.append({"name": f["name"], "current": f["allocation"], "change": change, "new": new_alloc})
    return result


def _market_comment(market):
    movers = [
        (fund, info["変化率"])
        for fund, info in market.items()
        if info.get("変化率") is not None and fund != "元本確保型"
    ]
    if not movers:
        return "市場データを取得できませんでした。"

    movers.sort(key=lambda x: abs(x[1]), reverse=True)
    top_fund, top_change = movers[0]
    direction = "上昇" if top_change > 0 else "下落"

    lines = [f"過去30日間で{top_fund}が{top_change:+.1f}%と最も{direction}しました。"]
    lines.append("各資産クラスの騰落率：")
    for fund, change in sorted(movers, key=lambda x: x[1], reverse=True):
        bar = "▲" if change > 0 else "▼"
        lines.append(f"  {bar} {fund}: {change:+.1f}%")
    return "\n".join(lines)


def analyze(dry_run=False):
    portfolio = load_portfolio()
    market = get_market_data(days=30)

    funds = portfolio.get("funds", [])
    target = portfolio.get("target_allocations", {})
    current = _category_totals(funds)

    lines = []

    # 市場動向
    lines.append("【市場動向】")
    lines.append(_market_comment(market))
    lines.append("")

    if not target:
        lines.append("【リバランス判定】目標配分が未設定のため判定できません。")
        return "\n".join(lines)

    # カテゴリ別の乖離を計算
    all_cats = set(list(current.keys()) + list(target.keys()))
    sells = []  # (category, diff)
    buys = []
    for cat in all_cats:
        cur = current.get(cat, 0)
        tgt = target.get(cat, 0)
        diff = cur - tgt
        if diff >= REBALANCE_THRESHOLD:
            sells.append((cat, diff))
        elif diff <= -REBALANCE_THRESHOLD:
            buys.append((cat, abs(diff)))

    sells.sort(key=lambda x: x[1], reverse=True)
    buys.sort(key=lambda x: x[1], reverse=True)

    if not sells and not buys:
        lines.append("【リバランス判定】")
        lines.append(f"全カテゴリの乖離が{REBALANCE_THRESHOLD}%未満です。変更不要です。")
        return "\n".join(lines)

    lines.append("【スイッチング指示】")
    lines.append("")

    # 売り（比率を下げる）
    if sells:
        lines.append("▼ 比率を下げる（スイッチング元）")
        for cat, diff in sells:
            cur = current.get(cat, 0)
            tgt = target.get(cat, 0)
            cat_funds = _funds_in_category(funds, cat)
            changes = _proportional_changes(cat_funds, -diff)
            lines.append(f"  [{cat}] 現在{cur:.0f}% → 目標{tgt:.0f}%（{diff:.0f}ポイント削減）")
            for c in changes:
                if cat == "元本確保型":
                    lines.append(f"    {c['name']}: {c['current']:.0f}% → {max(c['new'], 0):.0f}%（満期後に移換）")
                else:
                    lines.append(f"    {c['name']}: {c['current']:.0f}% → {max(c['new'], 0):.0f}%")
        lines.append("")

    # 買い（比率を上げる）
    if buys:
        lines.append("▲ 比率を上げる（スイッチング先）")
        for cat, diff in buys:
            cur = current.get(cat, 0)
            tgt = target.get(cat, 0)
            cat_funds = _funds_in_category(funds, cat)
            changes = _proportional_changes(cat_funds, diff)
            lines.append(f"  [{cat}] 現在{cur:.0f}% → 目標{tgt:.0f}%（{diff:.0f}ポイント増加）")
            for c in changes:
                lines.append(f"    {c['name']}: {c['current']:.0f}% → {c['new']:.0f}%")
        lines.append("")

    lines.append("推奨アクション: 見直し推奨（DC画面でスイッチングを実施してください）")

    # 63歳時点の予測残高
    plan = portfolio.get("plan", {})
    if plan and target:
        alloc_pct = {cat: pct / 100 for cat, pct in target.items()}
        rate = expected_return({cat: int(pct) for cat, pct in target.items()})
        pv   = plan["current_balance_man"] * 10_000
        p1y  = plan.get("years_to_retirement", 0)
        p1m  = plan.get("monthly_contribution", 0)
        p2y  = plan.get("ideco_years", 0) if plan.get("ideco_after_retirement") else 0
        p2m  = plan.get("ideco_monthly", 0) if plan.get("ideco_after_retirement") else 0

        std  = simulate_two_phase(pv, rate,           p1y, p1m, p2y, p2m)
        good = simulate_two_phase(pv, rate+GOOD_BOOST, p1y, p1m, p2y, p2m)
        bad  = simulate_two_phase(pv, rate+BAD_DRAG,   p1y, p1m, p2y, p2m)
        goal = plan.get("goal_age", 63)

        lines.append("")
        lines.append(f"【{goal}歳時点の予測残高（目標配分ベース）】")
        lines.append(f"  好調ケース: {good:,}円{'  ✅ 目標達成' if good >= TARGET else ''}")
        lines.append(f"  標準ケース: {std:,}円")
        lines.append(f"  不調ケース: {bad:,}円")

    report = "\n".join(lines)

    if dry_run:
        return f"[DRY RUN]\n{report}"

    return report


if __name__ == "__main__":
    result = analyze()
    print(result)
