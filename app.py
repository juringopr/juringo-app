from flask import Flask, render_template, request
import os
from analyzer import analyze_stock
from utils.krx_tickers import fetch_krx_tickers

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def normalize_ticker(ticker: str, market: str) -> str:
    t = (ticker or "").strip().upper()

    if market == "NASDAQ":
        t = t.replace(".", "-")  # BRK.B -> BRK-B
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
    반환: [{"symbol":"...", "name":"..."}]
    NASDAQ: Symbol|Security Name|... 형식에서 Security Name(2번째)만 사용
    KOSPI/KOSDAQ: 코드만 또는 코드|이름 가능
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

            # NASDAQ: 헤더 라인 제거 (파일에 헤더가 있을 때)
            if market == "NASDAQ":
                lower = line.lower()
                if lower.startswith("symbol|") or lower.startswith("symbol,"):
                    continue

                # ✅ Symbol|Security Name|Market Category|... → Security Name만
                if "|" in line:
                    parts = [p.strip() for p in line.split("|")]
                    symbol = parts[0] if len(parts) > 0 else ""
                    sec_name = parts[1] if len(parts) > 1 else ""
                else:
                    # 혹시 Symbol만 있는 파일이면 name은 공백
                    symbol = line
                    sec_name = ""

                # 심볼 이상치 제거 (공백 포함/너무 긴 것 등)
                if not symbol or (" " in symbol) or (len(symbol) > 15):
                    continue

                tickers.append({"symbol": symbol, "name": sec_name})
                continue

            # KOSPI/KOSDAQ txt 폴백
            if "|" in line:
                code, name = line.split("|", 1)
                symbol = code.strip()
                name = name.strip()
            else:
                symbol = line.strip()
                name = ""

            if symbol.isdigit():
                symbol = symbol.zfill(6)

            tickers.append({"symbol": symbol, "name": name})

        print(f"✅ [TXT] {market} tickers loaded: {len(tickers)}")
        return tickers

    except Exception as e:
        print(f"❌ [TXT] 로딩 오류({market}): {e}")
        return []

def load_tickers_with_names(market: str):
    """
    - KOSPI/KOSDAQ: KRX 캐시 우선, 실패 시 TXT 폴백
    - NASDAQ: TXT
    """
    if market in ("KOSPI", "KOSDAQ"):
        try:
            krx = fetch_krx_tickers(BASE_DIR)
            arr = krx.get(market, [])
            if arr:
                print(f"✅ [KRX] {market} tickers loaded: {len(arr)}")
                return arr
            print(f"⚠️ [KRX] {market} 리스트가 비었음 → TXT 폴백")
        except Exception as e:
            print(f"❌ [KRX] {market} 실패 → TXT 폴백: {e}")

        return _load_tickers_from_txt(market)

    if market == "NASDAQ":
        return _load_tickers_from_txt("NASDAQ")

    return []

def find_name_from_tickers(tickers, symbol: str) -> str:
    """
    드롭다운/입력값(final_ticker) 기준으로 tickers에서 name 찾기
    """
    s = (symbol or "").strip().upper()
    if not s:
        return ""
    for t in tickers:
        if (t.get("symbol") or "").strip().upper() == s:
            return (t.get("name") or "").strip()
    return ""

@app.route("/", methods=["GET", "POST"])
def index():
    result = ""
    chart_filename = None

    # ✅ GET에서도 market 선택 유지되게
    selected_market = request.form.get("market") or request.args.get("market") or "NASDAQ"

    selected_ticker = request.form.get("ticker", "").strip()
    custom_ticker = request.form.get("custom_ticker", "").strip().upper()

    # ✅ 시장에 맞는 tickers 로딩
    tickers = load_tickers_with_names(selected_market)

    final_ticker = custom_ticker if custom_ticker else selected_ticker

    # ✅ 화면에 표시할 종목명(모든 시장)
    selected_name = find_name_from_tickers(tickers, final_ticker)

    # ✅ POST인데 ticker가 없으면: "리스트 갱신용 제출"로 처리 (분석 X)
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
        selected_name=selected_name,   # ✅ 추가
        final_ticker=final_ticker,     # ✅ 추가(표시용)
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
