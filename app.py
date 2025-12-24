from flask import Flask, render_template, request
import os
from analyzer import analyze_stock

# ✅ KRX 티커 가져오기(캐시 포함)
from utils.krx_tickers import fetch_krx_tickers

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def normalize_ticker(ticker: str, market: str) -> str:
    t = (ticker or "").strip().upper()

    if market == "NASDAQ":
        # Yahoo: BRK.B -> BRK-B 형태
        t = t.replace(".", "-")
        return t

    if t.isdigit():
        t = t.zfill(6)

    if market == "KOSPI":
        return f"{t}.KS"
    if market == "KOSDAQ":
        return f"{t}.KQ"

    return t

def load_tickers_with_names(market: str):
    """
    반환: [{"symbol":"005930","name":"삼성전자"}, ...] 형태
    - KOSPI/KOSDAQ: KRX에서 자동 수집(캐시)
    - NASDAQ: 기존 txt(Symbol|Name|...) 사용
    """
    # ✅ KOSPI/KOSDAQ는 KRX 캐시 사용
    if market in ("KOSPI", "KOSDAQ"):
        try:
            krx = fetch_krx_tickers(BASE_DIR)
            return krx.get(market, [])
        except Exception as e:
            print(f"❌ KRX 티커 로딩 실패: {e}")
            # 실패 시 폴백: txt 시도 (있다면)
            # 아래 txt 로직으로 이어짐

    # NASDAQ 또는 폴백(txt)
    file_map = {
        "NASDAQ": "nasdaq_tickers.txt",
        "KOSPI": "kospi_tickers.txt",
        "KOSDAQ": "kosdaq_tickers.txt",
    }
    file_name = file_map.get(market)
    if not file_name:
        return []

    file_path = os.path.join(BASE_DIR, file_name)
    tickers = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

        if market == "NASDAQ":
            for line in lines:
                if "|" in line:
                    parts = line.split("|")
                    symbol = parts[0].strip()
                    name = parts[1].strip() if len(parts) > 1 else ""
                    if symbol:
                        tickers.append({"symbol": symbol, "name": name})
        else:
            # KOSPI/KOSDAQ txt가 코드만 있으면 name은 공백
            # 코드|이름 형태면 name도 표시
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if "|" in line:
                    code, name = line.split("|", 1)
                    tickers.append({"symbol": code.strip(), "name": name.strip()})
                else:
                    tickers.append({"symbol": line, "name": ""})

        return tickers

    except Exception as e:
        print(f"❌ 티커 txt 로딩 오류: {e}")
        return []

@app.route("/", methods=["GET", "POST"])
def index():
    result = ""
    chart_filename = None

    selected_market = request.form.get("market", "NASDAQ")
    selected_ticker = request.form.get("ticker", "").strip()
    custom_ticker = request.form.get("custom_ticker", "").strip().upper()

    tickers = load_tickers_with_names(selected_market)
    final_ticker = custom_ticker if custom_ticker else selected_ticker

    if request.method == "POST" and final_ticker:
        try:
            yf_ticker = normalize_ticker(final_ticker, selected_market)

            static_dir = os.path.join(app.root_path, "static")
            os.makedirs(static_dir, exist_ok=True)

            result, chart_filename = analyze_stock(yf_ticker, static_dir=static_dir)
        except Exception as e:
            result = f"⚠️ 오류 발생: {str(e)}"
            chart_filename = None

    return render_template(
        "index.html",
        tickers=tickers,
        result=result,
        chart_filename=chart_filename,
        selected_market=selected_market,
        selected_ticker=selected_ticker,
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
