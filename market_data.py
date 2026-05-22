import yfinance as yf
from datetime import datetime, timedelta

FUND_TICKERS = {
    "国内株式": "^N225",
    "外国株式": "^GSPC",
    "国内債券": "2621.T",
    "外国債券": "AGG",
    "元本確保型": None,
}


def get_market_data(days=30):
    results = {}
    end = datetime.now()
    start = end - timedelta(days=days)

    for fund_name, ticker in FUND_TICKERS.items():
        if ticker is None:
            results[fund_name] = {"変化率": 0.0, "説明": "元本確保型（市場連動なし）"}
            continue
        try:
            data = yf.download(ticker, start=start, end=end, progress=False)
            if data.empty:
                results[fund_name] = {"変化率": None, "説明": "データなし"}
                continue
            close = data["Close"]
            if hasattr(close, "squeeze"):
                close = close.squeeze()
            first = float(close.iloc[0])
            last = float(close.iloc[-1])
            change = (last - first) / first * 100
            results[fund_name] = {
                "変化率": round(change, 2),
                "最新値": round(last, 2),
                "ティッカー": ticker,
            }
        except TypeError as e:
            results[fund_name] = {"変化率": None, "説明": f"取得エラー（型エラー）: {e}"}
        except Exception as e:
            results[fund_name] = {"変化率": None, "説明": f"取得エラー: {e}"}

    return results


if __name__ == "__main__":
    data = get_market_data()
    for fund, info in data.items():
        print(f"{fund}: {info}")
