from flask import Flask, request, jsonify
import os
import psycopg2
from datetime import datetime

app = Flask(__name__)

# Load API key from environment variables
API_KEY = os.getenv("API_KEY")

if API_KEY:
    print("DEBUG: API Key Loaded ✅")  # No key output for security
else:
    print("ERROR: API Key is NOT being loaded! ❌")

# Database connection
DB_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# 🔹 Middleware to validate API Key for all requests
@app.before_request
def validate_api_key():
    api_key = request.headers.get("X-Api-Key") or request.headers.get("x-api-key")

    if not api_key:
        print("DEBUG: No API Key provided! ❌")
        return jsonify({"error": "Unauthorized - Missing API Key"}), 403

    if api_key != API_KEY:
        print("DEBUG: Unauthorized request - Invalid API Key ❌")
        return jsonify({"error": "Unauthorized - Invalid API Key"}), 403

# 🔹 Store memory in the database
@app.route("/remember", methods=["POST"])
def remember():
    try:
        data = request.get_json()
        topic = data.get("topic")
        details = data.get("details")
        timestamp = datetime.utcnow()

        cur.execute(
            "INSERT INTO memories (topic, details, timestamp) VALUES (%s, %s, %s) RETURNING id",
            (topic, details, timestamp)
        )
        memory_id = cur.fetchone()[0]
        conn.commit()

        print(f"DEBUG: Memory stored -> Topic: {topic}, ID: {memory_id} ✅")
        return jsonify({"message": "Memory stored successfully", "id": memory_id, "timestamp": timestamp.isoformat()}), 200
    except Exception as e:
        print(f"ERROR: Failed to store memory -> {str(e)} ❌")
        return jsonify({"error": "Internal Server Error"}), 500

# 🔹 Retrieve memory from the database
@app.route("/recall", methods=["GET"])
def recall():
    try:
        topic = request.args.get("topic")

        if not topic:
            print("DEBUG: Missing 'topic' parameter in request. ❌")
            return jsonify({"error": "Bad Request - Missing topic parameter"}), 400

        cur.execute("SELECT details, timestamp FROM memories WHERE topic = %s", (topic,))
        memory = cur.fetchone()

        if memory:
            print(f"DEBUG: Memory retrieved -> Topic: {topic} ✅")
            return jsonify({"topic": topic, "details": memory[0], "timestamp": memory[1].isoformat()}), 200
        else:
            print(f"DEBUG: No memory found for topic -> {topic} ❌")
            return jsonify({"error": "Memory not found"}), 404
    except Exception as e:
        print(f"ERROR: Failed to retrieve memory -> {str(e)} ❌")
        return jsonify({"error": "Internal Server Error"}), 500

# 🔹 Keep database connection alive
@app.route("/ping-db", methods=["HEAD", "GET"])
def ping_db():
    try:
        cur.execute("SELECT 1")
        return "Database is alive", 200
    except Exception as e:
        print(f"ERROR: Database connection failed -> {str(e)} ❌")
        return jsonify({"error": "Database Unreachable"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
