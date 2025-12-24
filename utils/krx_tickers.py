# utils/krx_tickers.py
import os
import json
import time
import requests
from datetime import datetime, timezone

KRX_GEN_OTP_URL = "https://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd"
KRX_DOWNLOAD_URL = "https://data.krx.co.kr/comm/fileDn/download_csv/download.cmd"

# 캐시 기본: 24시간
DEFAULT_TTL_SEC = 24 * 60 * 60

def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def _cache_path(base_dir: str) -> str:
    _ensure_dir(os.path.join(base_dir, "data"))
    return os.path.join(base_dir, "data", "krx_tickers_cache.json")

def _is_cache_valid(path: str, ttl_sec: int) -> bool:
    if not os.path.exists(path):
        return False
    mtime = os.path.getmtime(path)
    return (time.time() - mtime) < ttl_sec

def _download_krx_csv(mktId: str) -> list[dict]:
    """
    KRX 상장종목현황 CSV를 OTP 방식으로 다운로드해서 dict 리스트로 반환.
    mktId:
      - "STK" : KOSPI
      - "KSQ" : KOSDAQ
    """
    # 1) OTP 생성
    form = {
        "mktId": mktId,
        "share": "1",
        "csvxls_isNo": "false",
        "name": "fileDown",
        "url": "dbms/MDC/STAT/standard/MDCSTAT01901"
    }
    headers = {
        "Referer": "https://data.krx.co.kr/contents/MDC/STAT/standard/MDCSTAT01901.jspx",
        "User-Agent": "Mozilla/5.0"
    }

    otp_resp = requests.post(KRX_GEN_OTP_URL, data=form, headers=headers, timeout=20)
    otp_resp.raise_for_status()
    otp = otp_resp.text.strip()

    # 2) OTP로 CSV 다운로드
    down_resp = requests.post(KRX_DOWNLOAD_URL, data={"code": otp}, headers=headers, timeout=20)
    down_resp.raise_for_status()

    # 3) CSV 파싱 (KRX는 종종 cp949 인코딩)
    content = down_resp.content
    try:
        text = content.decode("cp949")
    except UnicodeDecodeError:
        text = content.decode("utf-8", errors="replace")

    # CSV를 pandas 없이 파싱 (의존성 최소화)
    # 헤더 예: "종목코드","종목명","시장구분",...
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return []

    # 간단 CSV split (KRX는 큰따옴표로 감싼 형태가 많음)
    import csv
    from io import StringIO

    reader = csv.DictReader(StringIO("\n".join(lines)))
    rows = []
    for r in reader:
        rows.append(r)
    return rows

def fetch_krx_tickers(base_dir: str, ttl_sec: int = DEFAULT_TTL_SEC) -> dict:
    """
    반환 형태:
    {
      "updated_at": "...",
      "KOSPI": [{"symbol":"005930","name":"삼성전자"}, ...],
      "KOSDAQ": [{"symbol":"035720","name":"카카오"}, ...]  # 예시
    }
    """
    cache_file = _cache_path(base_dir)

    # 캐시 유효하면 캐시 사용
    if _is_cache_valid(cache_file, ttl_sec):
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # KOSPI(STK) / KOSDAQ(KSQ) 각각 다운로드
    kospi_rows = _download_krx_csv("STK")
    kosdaq_rows = _download_krx_csv("KSQ")

    def _normalize(rows: list[dict]) -> list[dict]:
        out = []
        for r in rows:
            code = (r.get("종목코드") or "").strip()
            name = (r.get("종목명") or "").strip()

            # 종목코드가 숫자 6자리 형태로 유지되게
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

    # 캐시 저장
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data
