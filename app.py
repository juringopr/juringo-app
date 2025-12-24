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

def _load_tickers_from_txt(market: str):
    """
    TXT 폴백 로더:
    - NASDAQ: Symbol|Name|... 또는 Symbol만 있는 파일 모두 처리
    - KOSPI/KOSDAQ: 6자리 코드만 또는 코드|이름 모두 처리
    반환: [{"symbol":"...", "name":"..."}]
    """
    file_map = {
        "NASDAQ": "nasdaq_tickers.txt",
        "KOSPI": "kospi_tickers.txt",
        "KOSDAQ": "kosdaq_tickers.txt",
    }
    file_name = file_map.get(market)
    if not file_name:
        return []

    file_path = os.path.join(BASE_DIR, file_name)
    if not os.path.exists(file_path):
        print(f"❌ [TXT] 파일이 없음: {file_path}")
        return []

    tickers = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

        for raw in lines:
            line = (raw or "").strip()
            if not line:
                continue

            # 헤더/설명 라인 스킵(필요시 추가)
            # NASDAQ 파일에 'Symbol|Name|...' 같은 헤더가 있으면 제거
            if market == "NASDAQ":
                if line.lower().startswith("symbol|") or line.lower().startswith("symbol,"):
                    continue

            if "|" in line:
                left, right = line.split("|", 1)
                symbol = left.strip()
                name = right.strip()
            else:
                symbol = line.strip()
                name = ""

            # NASDAQ 심볼만 "정상"으로 남기기 (공백/이상문자 제거)
            if market == "NASDAQ":
                # 예: AAPL, MSFT, BRK.B 등
                # 심볼이 너무 길거나 공백 있으면 스킵
                if (" " in symbol) or (len(symbol) > 15):
                    continue
                # 빈 심볼 스킵
                if not symbol:
                    continue

            # 한국: 숫자면 6자리로 보정
            if market in ("KOSPI", "KOSDAQ"):
                sym = symbol.strip()
                if sym.isdigit():
                    sym = sym.zfill(6)
                symbol = sym

            tickers.append({"symbol": symbol, "name": name})

        print(f"✅ [TXT] {market} tickers loaded: {len(tickers)} from {file_path}")
        return tickers

    except Exception as e:
        print(f"❌ [TXT] 로딩 오류({market}): {e}")
        return []

def load_tickers_with_names(market: str):
    """
    반환: [{"symbol":"005930","name":"삼성전자"}, ...]
    우선순위:
      1) KOSPI/KOSDAQ: KRX 캐시(성공 시)
      2) 실패 시: TXT 폴백
      3) NASDAQ: TXT
    """
    # ✅ KOSPI/KOSDAQ는 KRX 시도 → 실패하면 무조건 TXT
    if market in ("KOSPI", "KOSDAQ"):
        try:
            krx = fetch_krx_tickers(BASE_DIR)
            arr = krx.get(market, [])
            if arr:
                print(f"✅ [KRX] {market} tickers loaded: {len(arr)}")
                return arr
            else:
                print(f"⚠️ [KRX] {market} 응답은 왔는데 리스트가 비었음 → TXT 폴백")
        except Exception as e:
            print(f"❌ [KRX] {market} 로딩 실패 → TXT 폴백: {e}")

        return _load_tickers_from_txt(market)

    # NASDAQ은 TXT 사용 (심볼/이름 파싱 견고하게)
    if market == "NASDAQ":
        return _load_tickers_from_txt("NASDAQ")

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
