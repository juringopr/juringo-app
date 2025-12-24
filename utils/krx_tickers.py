import os
import json
import time
import requests
from datetime import datetime, timezone

KRX_GEN_OTP_URL = "https://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd"
KRX_DOWNLOAD_URL = "https://data.krx.co.kr/comm/fileDn/download_csv/download.cmd"

DEFAULT_TTL_SEC = 24 * 60 * 60  # 24시간 캐시

def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def _cache_path(base_dir: str) -> str:
    _ensure_dir(os.path.join(base_dir, "data"))
    return os.path.join(base_dir, "data", "krx_tickers_cache.json")

def _is_cache_valid(path: str, ttl_sec: int) -> bool:
    if not os.path.exists(path):
        return False
    return (time.time() - os.path.getmtime(path)) < ttl_sec

def _download_krx_csv(mktId: str) -> list[dict]:
    """
    KRX '상장종목현황' CSV 다운로드.
    mktId:
      - STK: KOSPI
      - KSQ: KOSDAQ
    """
    form = {
        "mktId": mktId,
        "share": "1",
        "csvxls_isNo": "false",
        "name": "fileDown",
        "url": "dbms/MDC/STAT/standard/MDCSTAT01901",
    }
    headers = {
        "Referer": "https://data.krx.co.kr/contents/MDC/STAT/standard/MDCSTAT01901.jspx",
        "User-Agent": "Mozilla/5.0",
    }

    otp_resp = requests.post(KRX_GEN_OTP_URL, data=form, headers=headers, timeout=20)
    otp_resp.raise_for_status()
    otp = otp_resp.text.strip()

    down_resp = requests.post(KRX_DOWNLOAD_URL, data={"code": otp}, headers=headers, timeout=20)
    down_resp.raise_for_status()

    content = down_resp.content
    try:
        text = content.decode("cp949")
    except UnicodeDecodeError:
        text = content.decode("utf-8", errors="replace")

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return []

    import csv
    from io import StringIO

    reader = csv.DictReader(StringIO("\n".join(lines)))
    return list(reader)

def fetch_krx_tickers(base_dir: str, ttl_sec: int = DEFAULT_TTL_SEC) -> dict:
    """
    반환:
    {
      "updated_at": "...",
      "KOSPI": [{"symbol":"005930","name":"삼성전자"}, ...],
      "KOSDAQ": [{"symbol":"035720","name":"카카오"}, ...]
    }
    """
    cache_file = _cache_path(base_dir)

    if _is_cache_valid(cache_file, ttl_sec):
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    kospi_rows = _download_krx_csv("STK")
    kosdaq_rows = _download_krx_csv("KSQ")

    def _normalize(rows: list[dict]) -> list[dict]:
        out = []
        for r in rows:
            code = (r.get("종목코드") or "").strip()
            name = (r.get("종목명") or "").strip()
            if code.isdigit():
                code = code.zfill(6)
            if code:
                out.append({"symbol": code, "name": name})
        return out

    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "KOSPI": _normalize(kospi_rows),
        "KOSDAQ": _normalize(kosdaq_rows),
    }

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data
