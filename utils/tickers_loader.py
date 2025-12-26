import os
from utils.krx_master import get_krx_master_map

def _read_lines(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [ln.strip() for ln in f.read().splitlines() if ln.strip()]

def load_nasdaq_tickers(base_dir: str) -> list[dict]:
    """
    nasdaq_tickers.txt:
    Symbol|Security Name|Market Category|Test Issue|Financial Status|...
    → Security Name(2번째 컬럼)만 name으로 사용
    """
    path = os.path.join(base_dir, "nasdaq_tickers.txt")
    out = []
    for line in _read_lines(path):
        lower = line.lower()
        if lower.startswith("symbol|"):
            continue

        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            symbol = parts[0] if len(parts) > 0 else ""
            name = parts[1] if len(parts) > 1 else ""
        else:
            symbol = line
            name = ""

        if not symbol or (" " in symbol) or (len(symbol) > 15):
            continue

        out.append({"symbol": symbol, "name": name})
    return out

def load_kr_tickers_from_txt(base_dir: str, market: str) -> list[dict]:
    """
    kospi_tickers.txt / kosdaq_tickers.txt 에 6자리 코드만 있을 때,
    KRX 마스터맵으로 코드→종목명 매핑하여 반환
    """
    file_map = {
        "KOSPI": "kospi_tickers.txt",
        "KOSDAQ": "kosdaq_tickers.txt",
    }
    fname = file_map.get(market)
    if not fname:
        return []

    codes_path = os.path.join(base_dir, fname)
    codes = _read_lines(codes_path)
    if not codes:
        return []

    master = get_krx_master_map(base_dir)
    name_map = master.get(market, {})

    out = []
    for c in codes:
        code = c.strip()
        if code.isdigit():
            code = code.zfill(6)
        name = name_map.get(code, "")
        out.append({"symbol": code, "name": name})
    return out

def load_tickers_with_names(base_dir: str, market: str) -> list[dict]:
    """
    app.py에서 이 함수 하나만 호출하도록 “단일 진입점”
    """
    if market == "NASDAQ":
        return load_nasdaq_tickers(base_dir)
    if market in ("KOSPI", "KOSDAQ"):
        return load_kr_tickers_from_txt(base_dir, market)
    return []
