from flask import Flask
import threading

app = Flask(__name__)

@app.route("/")
def home():
    return "OK", 200

def keep_alive():
    threading.Thread(
        target=lambda: app.run(
            host="0.0.0.0",
            port=10000
        ),
        daemon=True
    ).start()
