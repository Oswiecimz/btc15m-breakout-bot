from flask import Flask, request, jsonify
import os
import requests
import datetime
from pybit.unified_trading import HTTP

app = Flask(__name__)

# ─────────────────────────────────────────────────────────
#  Config — задаётся через Railway Variables
# ─────────────────────────────────────────────────────────
BOT_TOKEN         = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID           = os.getenv("TELEGRAM_CHAT_ID")
BYBIT_API_KEY     = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET  = os.getenv("BYBIT_API_SECRET")
BYBIT_DEMO        = os.getenv("BYBIT_DEMO", "true").lower() == "true"
SYMBOL            = os.getenv("SYMBOL", "BTCUSDT")
LEVERAGE          = int(os.getenv("LEVERAGE", "10"))
POSITION_PCT      = float(os.getenv("POSITION_PCT", "0.30"))   # 30% баланса

# ─────────────────────────────────────────────────────────
#  Константы стратегии
# ─────────────────────────────────────────────────────────
TP_PCT = 0.0035   # +0.35%
SL_PCT = 0.0020   # -0.20%


# ─────────────────────────────────────────────────────────
#  Telegram
# ─────────────────────────────────────────────────────────
def send_telegram(message: str):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️  Telegram variables not configured")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": message},
            timeout=10,
        )
    except Exception as exc:
        print(f"Telegram error: {exc}")


# ─────────────────────────────────────────────────────────
#  Bybit helpers
# ─────────────────────────────────────────────────────────
def get_session() -> HTTP:
    """Возвращает сессию Bybit (Demo или Real)."""
    return HTTP(
        testnet=False,
        demo=BYBIT_DEMO,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET,
    )


def get_balance(session: HTTP) -> float:
    """Доступный баланс USDT."""
    resp = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
    return float(resp["result"]["list"][0]["totalAvailableBalance"])


def get_open_position(session: HTTP):
    """Возвращает открытую позицию по SYMBOL или None."""
    resp = session.get_positions(category="linear", symbol=SYMBOL)
    for pos in resp["result"]["list"]:
        if float(pos["size"]) > 0:
            return pos
    return None


def set_leverage(session: HTTP):
    """Устанавливает плечо (ошибку игнорируем — плечо уже может быть выставлено)."""
    try:
        session.set_leverage(
            category="linear",
            symbol=SYMBOL,
            buyLeverage=str(LEVERAGE),
            sellLeverage=str(LEVERAGE),
        )
    except Exception as exc:
        print(f"set_leverage (ignored): {exc}")


# ─────────────────────────────────────────────────────────
#  Торговая логика
# ─────────────────────────────────────────────────────────
def open_trade(side: str, entry_price: float):
    """
    side: "Buy"  → Long
          "Sell" → Short
    entry_price: цена закрытия свечи из TradingView
    """
    try:
        session = get_session()

        # 1. Проверяем, нет ли уже открытой позиции
        existing = get_open_position(session)
        if existing:
            pos_label = "LONG 🟢" if existing["side"] == "Buy" else "SHORT 🔴"
            send_telegram(
                f"⚠️ Сигнал проигнорирован\n"
                f"Позиция уже открыта: {pos_label} {SYMBOL}\n"
                f"Размер: {existing['size']} BTC"
            )
            return

        # 2. Устанавливаем плечо
        set_leverage(session)

        # 3. Считаем объём
        balance    = get_balance(session)
        margin_usd = balance * POSITION_PCT
        qty        = round((margin_usd * LEVERAGE) / entry_price, 3)

        if qty < 0.001:
            send_telegram(
                f"❌ Объём слишком мал: {qty} BTC\n"
                f"Баланс: ${balance:.2f} — пополни счёт или измени POSITION_PCT."
            )
            return

        # 4. Считаем TP и SL
        if side == "Buy":
            tp    = round(entry_price * (1 + TP_PCT), 1)
            sl    = round(entry_price * (1 - SL_PCT), 1)
            label = "🟢 LONG"
        else:
            tp    = round(entry_price * (1 - TP_PCT), 1)
            sl    = round(entry_price * (1 + SL_PCT), 1)
            label = "🔴 SHORT"

        # 5. Открываем рыночный ордер с TP/SL
        session.place_order(
            category    = "linear",
            symbol      = SYMBOL,
            side        = side,
            orderType   = "Market",
            qty         = str(qty),
            takeProfit  = str(tp),
            stopLoss    = str(sl),
            tpTriggerBy = "MarkPrice",
            slTriggerBy = "MarkPrice",
        )

        rr   = round(TP_PCT / SL_PCT, 2)
        mode = "DEMO 🧪" if BYBIT_DEMO else "REAL 💰"

        send_telegram(
            f"{label} {SYMBOL} — ордер выставлен\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"Вход:   {entry_price:.1f}\n"
            f"TP:     {tp:.1f}   (+{TP_PCT*100:.2f}%)\n"
            f"SL:     {sl:.1f}   (-{SL_PCT*100:.2f}%)\n"
            f"R:R:    1 : {rr}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"Баланс: ${balance:.2f}\n"
            f"Маржа:  ${margin_usd:.2f}\n"
            f"Объём:  {qty} BTC\n"
            f"Плечо:  {LEVERAGE}x\n"
            f"Режим:  {mode}"
        )

    except Exception as exc:
        send_telegram(f"❌ Ошибка при открытии сделки:\n{str(exc)}")
        print(f"Trade error: {exc}")


# ─────────────────────────────────────────────────────────
#  Маршруты Flask
# ─────────────────────────────────────────────────────────
@app.route("/")
def home():
    return "BTC 15M Breakout Bot is running"


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    print("=" * 50)
    print("SIGNAL:", datetime.datetime.now())
    print(data)
    print("=" * 50)

    signal = str(data.get("signal", "")).lower()
    price  = float(data.get("price", 0))

    if price <= 0:
        return jsonify({"status": "error", "message": "price missing or zero"})

    if signal == "long":
        open_trade("Buy", price)
    elif signal == "short":
        open_trade("Sell", price)
    else:
        send_telegram(f"📩 TEST SIGNAL\n{data}")

    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
