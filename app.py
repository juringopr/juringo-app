from flask import Flask, render_template, request
import os
from analyzer import analyze_stock
from utils.tickers_loader import load_tickers_with_names  # ✅ 단일 진입점

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def normalize_ticker(ticker: str, market: str) -> str:
    t = (ticker or "").strip().upper()
    if market == "NASDAQ":
        return t.replace(".", "-")
    if t.isdigit():
        t = t.zfill(6)
    if market == "KOSPI":
        return f"{t}.KS"
    if market == "KOSDAQ":
        return f"{t}.KQ"
    return t

def find_name_from_tickers(tickers, symbol: str) -> str:
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

    selected_market = request.form.get("market") or request.args.get("market") or "NASDAQ"
    selected_ticker = request.form.get("ticker", "").strip()
    custom_ticker = request.form.get("custom_ticker", "").strip().upper()

    tickers = load_tickers_with_names(BASE_DIR, selected_market)

    final_ticker = custom_ticker if custom_ticker else selected_ticker
    selected_name = find_name_from_tickers(tickers, final_ticker)

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
        selected_name=selected_name,
        final_ticker=final_ticker,
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
