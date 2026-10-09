import os
import random
import requests
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from io import BytesIO
from telegram import Bot
import asyncio

# ← این خط رو درست کن (اسم Secret رو بذار، نه توکن)
TOKEN = os.environ["TELEGRAM_TOKEN"]

OWNER_IDS = ["8890419149", "6930861147"]
BATCH_SIZE = 3
BREAKOUT_THRESHOLD = 19

ALL_SYMBOLS = [
    "DOGEUSDT", "SHIBUSDT", "PEPEUSDT", "BONKUSDT", "WIFUSDT",
    "FLOKIUSDT", "TRXUSDT", "XLMUSDT", "ADAUSDT", "MATICUSDT",
    "DOTUSDT", "LTCUSDT", "XRPUSDT", "ALGOUSDT", "VETUSDT",
    "HBARUSDT", "EGLDUSDT", "ONEUSDT", "ZILUSDT", "IOTAUSDT",
    "ANKRUSDT", "CKBUSDT", "HOTUSDT", "RSRUSDT", "JASMYUSDT",
    "GALAUSDT", "SANDUSDT", "MANAUSDT", "CHZUSDT", "ENJUSDT",
    "USUSDT"
]

TIMEFRAMES = ["5m", "15m", "1h", "4h"]


def get_klines(symbol, interval):
    try:
        url = f"https://api.binance.us/api/v3/klines?symbol={symbol}&interval={interval}&limit=100"
        r = requests.get(url, timeout=10)
        data = r.json()
        if not isinstance(data, list) or len(data) < 50:
            return None
        df = pd.DataFrame(data, columns=[
            "time", "open", "high", "low", "close", "volume",
            "close_time", "qav", "trades", "tbb", "tbq", "ignore"
        ])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        return df
    except Exception as e:
        print(f"❌ {symbol}: {e}")
        return None


def calc_bb(df, period=20, mult=2):
    closes = df["close"]
    mid = closes.rolling(period).mean()
    std = closes.rolling(period).std()
    upper = mid + mult * std
    lower = mid - mult * std
    return upper, mid, lower


def make_candlestick(df, symbol, interval):
    df = df.tail(60).reset_index(drop=True)
    upper, mid, lower = calc_bb(df)

    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")

    for i, row in df.iterrows():
        color = "#22c55e" if row["close"] >= row["open"] else "#ef4444"
        ax.plot([i, i], [row["low"], row["high"]], color=color, linewidth=1)
        ax.add_patch(plt.Rectangle(
            (i - 0.3, min(row["open"], row["close"])),
            0.6, abs(row["close"] - row["open"]),
            facecolor=color, edgecolor=color, alpha=0.9
        ))

    ax.plot(range(len(df)), upper.values, color="#ff8c00", linewidth=1.5, label="BOLL UP")
    ax.plot(range(len(df)), mid.values, color="#ff8c00", linewidth=1.5, linestyle="--", label="BOLL")
    ax.plot(range(len(df)), lower.values, color="#ff8c00", linewidth=1.5, label="BOLL LB")

    ax.set_title(f"{symbol} - {interval}", color="white", fontsize=14, weight="bold")
    ax.tick_params(colors="#888888")
    for spine in ax.spines.values():
        spine.set_color("#333333")
    ax.grid(True, alpha=0.1, color="white")
    ax.legend(facecolor="#0d1117", edgecolor="#333333", labelcolor="white", loc="upper left")

    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=100, bbox_inches="tight", facecolor="#0d1117")
    plt.close(fig)
    buf.seek(0)
    return buf


async def send_photo(bot, buf, caption):
    for id in OWNER_IDS:
        try:
            await bot.send_photo(chat_id=id, photo=buf, caption=caption, parse_mode="HTML")
            print(f"✅ Photo sent to {id}")
        except Exception as e:
            print(f"❌ Error sending to {id}: {e}")


async def check_signal(bot, symbol, interval):
    df = get_klines(symbol, interval)
    if df is None:
        return

    last = df.iloc[-1]
    close = last["close"]
    open_price = last["open"]

    if close > 1:
        return

    upper, mid, lower = calc_bb(df)
    last_upper = upper.iloc[-1]
    last_lower = lower.iloc[-1]
    width = last_upper - last_lower

    if pd.isna(width) or width == 0:
        return

    if close <= open_price:
        return

    if close <= last_upper:
        return

    breakout_pct = ((close - last_upper) / width) * 100
    if breakout_pct < BREAKOUT_THRESHOLD:
        return

    buf = make_candlestick(df, symbol, interval)
    caption = (
        f"🚀 <b>سیگنال شیت‌کوین</b>\n\n"
        f"📊 <b>{symbol}</b> - {interval}\n"
        f"💰 قیمت: <code>{close:.6f}</code>\n"
        f"🔥 بیرون‌زدگی: <b>{breakout_pct:.2f}%</b>"
    )
    await send_photo(bot, buf, caption)
    print(f"✅ {symbol} {interval} | {breakout_pct:.2f}%")


async def main():
    bot = Bot(token=TOKEN)
    batch = random.sample(ALL_SYMBOLS, BATCH_SIZE)
    print(f"🔍 Checking: {', '.join(batch)}")

    for symbol in batch:
        for tf in TIMEFRAMES:
            await check_signal(bot, symbol, tf)
            await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())
