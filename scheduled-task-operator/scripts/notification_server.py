from flask import Flask, request
import subprocess

app = Flask(__name__)

@app.route("/notify", methods=["POST"])
def notify():
    data = request.json
    name = data.get("name", "Unknown")
    artist = data.get("artist", "Unknown")
    url = data.get("url", "")

    subprocess.run([
        "osascript", "-e",
        f'display notification "🎵 {name} — {artist}" with title "Your Morning Song" subtitle "{url}"'
    ])

    print(f"Notification sent: {name} — {artist}")
    return {"status": "ok"}, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)