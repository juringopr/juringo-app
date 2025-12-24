from flask import Flask, render_template, request
import os
from analyzer import analyze_stock

app = Flask(__name__)

# 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ✅ [추가] 티커 정규화 함수: 시장별 yfinance 포맷으로 변환
def normalize_ticker(ticker: str, market: str) -> str:
    t = (ticker or "").strip().upper()

    # NASDAQ/미국: 야후 포맷은 BRK.B -> BRK-B 형태가 많음
    if market == "NASDAQ":
        # 점(.)이 들어간 티커를 하이픈으로 교체 (BRK.B, BF.B 등)
        t = t.replace(".", "-")
        return t

    # 한국: 숫자 종목코드면 6자리로 보정 후 suffix 부여
    if t.isdigit():
        t = t.zfill(6)

    if market == "KOSPI":
        return f"{t}.KS"
    if market == "KOSDAQ":
        return f"{t}.KQ"

    return t

# 📌 티커 로딩 함수
def load_tickers(market):
    file_map = {
        "NASDAQ": "nasdaq_tickers.txt",
        "KOSPI": "kospi_tickers.txt",
        "KOSDAQ": "kosdaq_tickers.txt"
    }
    file_name = file_map.get(market)
    if not file_name:
        return []

    file_path = os.path.join(BASE_DIR, file_name)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
            if market == "NASDAQ":
                # Symbol|Name|... 형식에서 Symbol만 추출
                return [line.split("|")[0] for line in lines if "|" in line]
            else:
                return lines
    except Exception as e:
        print(f"❌ 티커 로딩 오류: {e}")
        return []

# 📌 기본 라우트
@app.route("/", methods=["GET", "POST"])
def index():
    result = ""
    chart_filename = None  # GET에서도 항상 존재

    selected_market = request.form.get("market", "NASDAQ")
    selected_ticker = request.form.get("ticker", "").strip()
    custom_ticker = request.form.get("custom_ticker", "").strip().upper()

    # 티커 리스트 로딩
    tickers = load_tickers(selected_market)

    final_ticker = custom_ticker if custom_ticker else selected_ticker

    if request.method == "POST" and final_ticker:
        try:
            # ✅ [추가] 시장에 맞게 yfinance 티커로 변환
            yf_ticker = normalize_ticker(final_ticker, selected_market)

            # static 폴더 절대경로
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

# Render 배포용
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
