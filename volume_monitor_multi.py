import yfinance as yf
import pandas as pd
import time
from datetime import datetime
import pytz
import requests
import os

# =========================
# TELEGRAM HELPER
# =========================
def send_telegram(msg):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")

    if not token or not chat_id:
        print("⚠️ Telegram ENV fehlt")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": msg,
        "disable_web_page_preview": True
    }

    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print("Telegram Fehler:", e)

# =========================
# CONFIG
# =========================
TICKERS = {
    "QNC.V":  {"name": "Quantum eMotion",  "market": "US"},
    "QBTS":   {"name": "D-Wave Quantum",   "market": "US"},
    "KLAC":   {"name": "KLA Corporation",  "market": "US"},
    "STX":    {"name": "Seagate Tech",     "market": "US"},
    "WDC":    {"name": "Western Digital",  "market": "US"},
    "APH":    {"name": "Amphenol",         "market": "US"},
    "CLS":    {"name": "Celestica",        "market": "US"},

    # Beispiel für EU später:
    # "ENR.DE": {"name": "Siemens Energy", "market": "EU"},
}

LOOKBACK_DAYS = 20
CHECK_INTERVAL = 300  # 5 Minuten

ALERT_1 = 2.0   # ⚠️
ALERT_2 = 3.5   # 🚨

TZ = pytz.timezone("Europe/Vienna")

# =========================
# MARKET SESSION LOGIC
# =========================
def market_open(market):
    now = datetime.now(TZ)

    if now.weekday() >= 5:  # Wochenende
        return False

    # 🇺🇸 US: 15:30–22:00
    if market == "US":
        return (
            (now.hour > 15 or (now.hour == 15 and now.minute >= 30))
            and now.hour < 22
        )

    # 🇪🇺 EU: 09:00–17:30
    if market == "EU":
        return (
            now.hour >= 9
            and (now.hour < 17 or (now.hour == 17 and now.minute <= 30))
        )

    return False

# =========================
# DATA FUNCTIONS
# =========================
def get_avg_volume(ticker):
    df = yf.download(
        ticker,
        period=f"{LOOKBACK_DAYS + 5}d",
        interval="1d",
        auto_adjust=False,
        progress=False
    )
    if df.empty:
        return None

    avg = df["Volume"].tail(LOOKBACK_DAYS).mean()
    return float(avg.iloc[0]) if isinstance(avg, pd.Series) else float(avg)

def get_today_volume(ticker):
    df = yf.download(
        ticker,
        period="1d",
        interval="5m",
        auto_adjust=False,
        progress=False
    )
    if df.empty:
        return None

    total = df["Volume"].sum()
    return float(total.iloc[0]) if isinstance(total, pd.Series) else float(total)

# =========================
# MAIN
# =========================
def main():
    print("📊 Multi-Session Volume Monitor gestartet\n")

    avg_volumes = {}
    for ticker in TICKERS:
        avg = get_avg_volume(ticker)
        if avg:
            avg_volumes[ticker] = avg
            print(f"{ticker:<6} | Avg {LOOKBACK_DAYS}d Volume: {int(avg):,}")
        else:
            print(f"{ticker:<6} | ❌ No avg volume")

    print("\nMonitoring läuft …\n")

    while True:
        try:
            now_str = datetime.now(TZ).strftime("%H:%M:%S")

            for ticker, meta in TICKERS.items():
                if ticker not in avg_volumes:
                    continue

                if not market_open(meta["market"]):
                    continue

                today_vol = get_today_volume(ticker)
                if not today_vol:
                    continue

                ratio = today_vol / avg_volumes[ticker]

                if ratio >= ALERT_2:
                    msg = f"🚨 {ticker} ({meta['market']}) EXTREMES VOLUMEN\n{ratio:.2f}x Ø"
                    print(f"[{now_str}] {msg}")
                    send_telegram(msg)

                elif ratio >= ALERT_1:
                    msg = f"⚠️ {ticker} ({meta['market']}) Volumenanstieg\n{ratio:.2f}x Ø"
                    print(f"[{now_str}] {msg}")
                    send_telegram(msg)

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n🛑 Monitoring gestoppt.")
            break

        except Exception as e:
            print("❌ Fehler:", e)
            time.sleep(600)

if __name__ == "__main__":
    main()
