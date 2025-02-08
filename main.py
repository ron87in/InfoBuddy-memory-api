import os
import psycopg2
from flask import Flask, request, jsonify

app = Flask(__name__)

# Fetch API Key and Database URL from Render’s Environment Variables
DB_URL = os.getenv("DATABASE_URL")
API_KEY = os.getenv("API_KEY")

def get_db_connection():
    return psycopg2.connect(DB_URL)

@app.route("/recall", methods=["GET"])
def recall_memory():
    user_key = request.headers.get("X-API-KEY")
    if user_key != API_KEY:
        return jsonify({"error": "Unauthorized"}), 403

    topic = request.args.get("topic")
    if not topic:
        return jsonify({"error": "Missing topic"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT details FROM memory WHERE topic = %s", (topic,))
        result = cursor.fetchone()
        conn.close()

        if result:
            return jsonify({"memory": result[0]})
        else:
            return jsonify({"memory": "No memory found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/remember", methods=["POST"])
def remember_memory():
    user_key = request.headers.get("X-API-KEY")
    if user_key != API_KEY:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    topic = data.get("topic")
    details = data.get("details")

    if not topic or not details:
        return jsonify({"error": "Missing topic or details"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO memory (topic, details) VALUES (%s, %s) ON CONFLICT (topic) DO UPDATE SET details = EXCLUDED.details",
            (topic, details),
        )
        conn.commit()
        conn.close()
        return jsonify({"status": "Memory saved"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)