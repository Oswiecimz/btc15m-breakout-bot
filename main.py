from flask import Flask, request, jsonify
import os
import requests
import datetime

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram variables not configured")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": message
        },
        timeout=10
    )


@app.route("/")
def home():
    return "BTC 15M Breakout Bot is running"


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    print("=" * 50)
    print("SIGNAL RECEIVED")
    print(datetime.datetime.now())
    print(data)
    print("=" * 50)

    signal = str(data.get("signal", "")).lower()
    symbol = data.get("symbol", "BTCUSDT")
    price = float(data.get("price", 0))

    if price > 0:

        if signal == "long":
            tp = price * 1.0035
            sl = price * 0.9975

            msg = (
                f"🚀 LONG {symbol}\n\n"
                f"Цена: {price:.2f}\n"
                f"TP: {tp:.2f}\n"
                f"SL: {sl:.2f}"
            )

            send_telegram(msg)

        elif signal == "short":
            tp = price * 0.9965
            sl = price * 1.0025

            msg = (
                f"🔻 SHORT {symbol}\n\n"
                f"Цена: {price:.2f}\n"
                f"TP: {tp:.2f}\n"
                f"SL: {sl:.2f}"
            )

            send_telegram(msg)

        else:
            send_telegram(
                f"📩 TEST SIGNAL\n\n{data}"
            )

    return jsonify({
        "status": "ok"
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
