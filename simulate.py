"""
DC年金シミュレーター
目標額に到達するまでの年数と、配分ごとの期待リターンを計算する
"""

MONTHLY_CONTRIBUTION = 34_300
ANNUAL_CONTRIBUTION = MONTHLY_CONTRIBUTION * 12
TARGET = 15_000_000

# 資産クラス別の想定年率リターン（過去実績ベースの概算）
ASSET_RETURNS = {
    "元本確保型": 0.003,
    "国内債券":   0.020,
    "外国債券":   0.040,
    "国内株式":   0.065,
    "外国株式":   0.075,
}

SCENARIOS = {
    "現在の配分（元本確保型10 国内債券23 国内株式23 外国債券11 外国株式33）": {
        "元本確保型": 10, "国内債券": 23, "国内株式": 23, "外国債券": 11, "外国株式": 33,
    },
    "目標の配分（元本確保型0 国内債券10 国内株式45 外国債券10 外国株式35）": {
        "元本確保型": 0,  "国内債券": 10, "国内株式": 45, "外国債券": 10, "外国株式": 35,
    },
    "積極型（元本確保型0 国内債券5 国内株式50 外国債券5 外国株式40）": {
        "元本確保型": 0,  "国内債券": 5,  "国内株式": 50, "外国債券": 5,  "外国株式": 40,
    },
    "超積極型（国内株式55 外国株式45）": {
        "元本確保型": 0,  "国内債券": 0,  "国内株式": 55, "外国債券": 0,  "外国株式": 45,
    },
}

# 好調ケース・不調ケースは期待リターンに対してこれだけ上下にブレる想定
GOOD_BOOST  = 0.035   # +3.5%
BAD_DRAG    = -0.035  # -3.5%


def expected_return(alloc: dict) -> float:
    return sum(alloc[cat] / 100 * ASSET_RETURNS[cat] for cat in alloc)


def simulate_two_phase(pv: int, rate: float,
                       phase1_years: float, phase1_monthly: int,
                       phase2_years: float, phase2_monthly: int) -> int:
    """定年前後で掛金が変わる2フェーズシミュレーション"""
    balance = float(pv)

    # フェーズ1（月次複利）
    months1 = int(round(phase1_years * 12))
    monthly_rate = (1 + rate) ** (1 / 12) - 1
    for _ in range(months1):
        balance = balance * (1 + monthly_rate) + phase1_monthly

    # フェーズ2（月次複利）
    months2 = int(round(phase2_years * 12))
    for _ in range(months2):
        balance = balance * (1 + monthly_rate) + phase2_monthly

    return int(balance)


def run(current_balance: int,
        phase1_years: float = 2.83,   # 定年まで（2年10ヶ月）
        phase2_years: float = 3.0,    # 定年後継続期間
        phase1_monthly: int = MONTHLY_CONTRIBUTION,
        phase2_monthly: int = 0):     # 定年後の掛金（0=なし）

    total_years = phase1_years + phase2_years

    print(f"\n{'='*64}")
    print(f" DC シミュレーション（63歳時点）")
    print(f" 現在評価額  : {current_balance:,}円")
    print(f" 定年まで    : {phase1_years:.1f}年（月{phase1_monthly:,}円 拠出）")
    print(f" 定年後継続  : {phase2_years:.0f}年（月{phase2_monthly:,}円 拠出）")
    print(f" 合計期間    : {total_years:.1f}年")
    print(f" 目標        : {TARGET:,}円")
    print(f"{'='*64}")

    for label, alloc in SCENARIOS.items():
        base_rate = expected_return(alloc)
        good_rate = base_rate + GOOD_BOOST
        bad_rate  = base_rate + BAD_DRAG

        std  = simulate_two_phase(current_balance, base_rate,
                                  phase1_years, phase1_monthly,
                                  phase2_years, phase2_monthly)
        good = simulate_two_phase(current_balance, good_rate,
                                  phase1_years, phase1_monthly,
                                  phase2_years, phase2_monthly)
        bad  = simulate_two_phase(current_balance, bad_rate,
                                  phase1_years, phase1_monthly,
                                  phase2_years, phase2_monthly)

        reach = "✅ 達成" if good >= TARGET else "❌ 未達"

        print(f"\n■ {label}")
        print(f"  期待リターン: {base_rate*100:.1f}%/年")
        print(f"  好調ケース（+{GOOD_BOOST*100:.1f}%）: {good:>12,}円  {reach}")
        print(f"  標準ケース            : {std:>12,}円")
        print(f"  不調ケース（{BAD_DRAG*100:.1f}%）: {bad:>12,}円")

    print()


def run_from_plan(plan: dict):
    """portfolio.jsonのplanセクションからシミュレーションを実行"""
    pv = plan["current_balance_man"] * 10_000
    phase1_years   = plan["years_to_retirement"]
    phase1_monthly = plan["monthly_contribution"]
    phase2_years   = plan["ideco_years"] if plan.get("ideco_after_retirement") else 0
    phase2_monthly = plan["ideco_monthly"] if plan.get("ideco_after_retirement") else 0

    run(pv,
        phase1_years=phase1_years,
        phase2_years=phase2_years,
        phase1_monthly=phase1_monthly,
        phase2_monthly=phase2_monthly)


if __name__ == "__main__":
    import sys, json
    from pathlib import Path

    plan_file = Path(__file__).parent / "portfolio.json"
    if plan_file.exists():
        with open(plan_file, encoding="utf-8") as f:
            portfolio = json.load(f)
        plan = portfolio.get("plan", {})
    else:
        plan = {}

    if plan:
        run_from_plan(plan)
    else:
        # フォールバック
        pv = 725 * 10_000
        print("\n【定年後iDeCo継続】")
        run(pv, phase2_monthly=23_000)
