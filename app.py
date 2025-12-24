from flask import Flask, render_template, request
import os
from analyzer import analyze_stock  # 분석 함수

app = Flask(__name__)

# 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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
    chart_filename = None  # ✅ GET에서도 항상 존재하도록 (UnboundLocalError 방지)

    selected_market = request.form.get("market", "NASDAQ")
    selected_ticker = request.form.get("ticker", "").strip()
    custom_ticker = request.form.get("custom_ticker", "").strip().upper()

    # 티커 리스트 로딩
    tickers = load_tickers(selected_market)

    final_ticker = custom_ticker if custom_ticker else selected_ticker

    if request.method == "POST" and final_ticker:
        try:
            # ✅ Render/Flask에서 static 경로 안정화
            static_dir = os.path.join(app.root_path, "static")
            os.makedirs(static_dir, exist_ok=True)

            result, chart_filename = analyze_stock(final_ticker, static_dir=static_dir)
        except Exception as e:
            result = f"⚠️ 오류 발생: {str(e)}"
            chart_filename = None

    return render_template(
        "index.html",
        tickers=tickers,
        result=result,
        chart_filename=chart_filename,  # ✅ 파일명만 넘김
        selected_market=selected_market,
        selected_ticker=selected_ticker,
    )

# ✅ Render 배포용 실행 (포트 바인딩 필수)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
