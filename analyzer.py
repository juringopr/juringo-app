import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import os
import uuid

def analyze_stock(ticker: str):
    try:
        # ✅ 데이터 불러오기
        df = yf.download(ticker, period="2y", auto_adjust=True)
        if df.empty or len(df) < 200:
            return f"❌ [{ticker}] 가격 데이터가 부족하거나 비어 있습니다.", None

        sp500 = yf.download("^GSPC", start=df.index[0], end=df.index[-1], auto_adjust=True)
        if sp500.empty:
            return f"❌ S&P500 지수 데이터를 불러오지 못했습니다.", None

        # ✅ 이동평균 계산
        df["MA21"] = df["Close"].rolling(window=21).mean()
        df["MA40"] = df["Close"].rolling(window=40).mean()
        df["MA50"] = df["Close"].rolling(window=50).mean()
        df["MA150"] = df["Close"].rolling(window=150).mean()
        df["MA200"] = df["Close"].rolling(window=200).mean()
        df["Volume_MA50"] = df["Volume"].rolling(window=50).mean()
        df["High_52w"] = df["Close"].rolling(window=252).max()
        df["Low_52w"] = df["Close"].rolling(window=252).min()

        # ✅ 수익률 계산
        df["Ret"] = df["Close"].pct_change().rolling(5).mean()
        sp500["Ret"] = sp500["Close"].pct_change().rolling(5).mean()

        df.dropna(inplace=True)
        if df.empty:
            return f"❌ [{ticker}] 유효한 데이터가 충분하지 않습니다.", None

        sp500 = sp500.reindex(df.index).ffill()
        if sp500.empty:
            return f"❌ S&P500 데이터 처리 중 문제가 발생했습니다.", None

        # ✅ 주요 지표 추출
        latest = df.iloc[-1]
        current_price = latest["Close"].item()
        high_52w = latest["High_52w"].item()
        low_52w = latest["Low_52w"].item()
        current_volume = latest["Volume"].item()
        avg_volume_50 = latest["Volume_MA50"].item()
        ma21 = latest["MA21"].item()
        ma40 = latest["MA40"].item()
        ma50 = latest["MA50"].item()
        ma150 = latest["MA150"].item()
        ma200 = latest["MA200"].item()

        # ✅ 조건 계산
        rel_strength = (df["Ret"].tail(10) / sp500["Ret"].tail(10)).mean()
        from_high = (high_52w - current_price) / high_52w * 100
        from_low = (current_price - low_52w) / low_52w * 100

        handle_period = df.tail(10)
        handle_high_val = handle_period["Close"].max().item()
        handle_low_val = handle_period["Close"].min().item()
        handle_drop_pct = (handle_high_val - handle_low_val) / handle_high_val * 100
        handle_volume_avg = handle_period["Volume"].mean().item()
        handle_above_ma50 = handle_high_val > ma50

        pre_handle = df.tail(15).head(5)
        red_vol = pre_handle[(pre_handle["Close"] < pre_handle["Open"]) & (pre_handle["Volume"] > avg_volume_50)]
        no_heavy_red_volume = red_vol.empty

        recent_volumes = df["Volume"].tail(10).values
        recent_avg_volume = df["Volume_MA50"].tail(10).values
        volume_spike = (recent_volumes > recent_avg_volume * 1.3).any()

        ma200_trend = df["MA200"].tail(30)
        ma200_uptrend = ma200_trend.is_monotonic_increasing

        # ✅ 조건 통합
        all_conditions_met = (
            handle_above_ma50 and
            ma50 > ma150 > ma200 and
            ma200_uptrend and
            (high_52w - handle_high_val) / high_52w * 100 <= 25 and
            (handle_high_val - low_52w) / low_52w * 100 >= 25 and
            volume_spike and
            rel_strength > 3 and
            handle_drop_pct <= 10 and
            handle_volume_avg < avg_volume_50 and
            no_heavy_red_volume
        )

        # ✅ 결과 메시지
        result = f"""
✅ 현재 종가: ${current_price:.2f}
📉 52주 고점 대비 하락률: {from_high:.2f}%
📈 52주 저점 대비 상승률: {from_low:.2f}%
📦 현재 거래량: {current_volume:,.0f}
📊 50일 평균 거래량: {avg_volume_50:,.0f}

📏 손잡이 조건 분석:
• 손잡이 조정폭: {handle_drop_pct:.2f}%
• 손잡이 거래량 평균: {handle_volume_avg:,.0f}
• 손잡이 MA50 위: {'✅ Yes' if handle_above_ma50 else '❌ No'}
• MA 정배열 상태: {'✅ Yes' if ma50 > ma150 > ma200 else '❌ No'}
• MA200 30일 상승 추세: {'✅ Yes' if ma200_uptrend else '❌ No'}
• 상대강도 (지수 대비): {rel_strength:.2f}배 {'✅ 강세' if rel_strength > 3 else '❌ 약세'}
• 손잡이 형성 전 음봉 고거래량 없음: {'✅ Yes' if no_heavy_red_volume else '❌ 있음'}
• 거래량 돌파: {'✅ Yes' if volume_spike else '❌ No'}
"""

        if all_conditions_met:
            buy_trigger_price = round(handle_high_val * 1.01, 2)
            target_1 = round(buy_trigger_price * 1.15, 2)
            target_2 = round(buy_trigger_price * 1.25, 2)
            stop_loss = round(min(ma21, ma40), 2)

            result += f"""
🏆 {ticker}는 Cup with Handle 조건을 **완벽하게 충족**합니다!

💸 [매수 타점]
• 손잡이 상단: ${handle_high_val:.2f}
• 매수 가격 (손잡이 상단 +1%): ${buy_trigger_price:.2f}

🎯 [익절 타점]
• 1차 익절가 (15%): ${target_1:.2f}
• 2차 익절가 (25%): ${target_2:.2f}

⚠️ [손절 기준]
• 손절가 (MA21/MA40 중 낮은 값): ${stop_loss:.2f}
"""
        else:
            result += f"\n❌ {ticker}는 Cup with Handle 조건을 **아직 모두 충족하지 않습니다.**"

        # ✅ 차트 저장
        chart_filename = f"static/chart_{uuid.uuid4().hex}.png"
        plt.figure(figsize=(14, 6))
        plt.plot(df["Close"], label="종가", linewidth=2)
        plt.plot(df["MA21"], label="MA21", linestyle="--")
        plt.plot(df["MA40"], label="MA40", linestyle="--")
        plt.plot(df["MA50"], label="MA50", linestyle="--")
        plt.plot(df["MA150"], label="MA150", linestyle="--")
        plt.plot(df["MA200"], label="MA200", linestyle="--")
        plt.title(f"{ticker} - Cup with Handle 조건 분석")
        plt.xlabel("날짜")
        plt.ylabel("가격")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(chart_filename)
        plt.close()

        return result, chart_filename

    except Exception as e:
        return f"⚠️ 오류 발생: {str(e)}", None
