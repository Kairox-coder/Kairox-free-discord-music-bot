import os
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "OK", 200

def keep_alive():
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
