from flask import Flask, request, jsonify
import datetime

app = Flask(__name__)

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

    return jsonify({
        "status": "ok",
        "received": data
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
