from flask import Flask, request, jsonify
import psycopg2
import os

app = Flask(__name__)

# Retrieve API Key from environment variable
API_KEY = os.getenv("API_KEY")

# Database connection function
def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# Middleware to check API Key
def verify_api_key():
    key = request.headers.get("X-API-KEY")
    if key != API_KEY:
        return jsonify({"error": "Unauthorized access"}), 403

# Endpoint to save memory
@app.route("/remember", methods=["POST"])
def remember():
    error = verify_api_key()
    if error: return error  # Deny request if API key is wrong

    data = request.json
    topic = data.get("topic")
    details = data.get("details")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO memory (topic, details) VALUES (%s, %s) ON CONFLICT (topic) DO UPDATE SET details = EXCLUDED.details", (topic, details))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "Memory saved"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint to recall memory
@app.route("/recall", methods=["GET"])
def recall():
    error = verify_api_key()
    if error: return error  # Deny request if API key is wrong

    topic = request.args.get("topic")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT details FROM memory WHERE topic = %s", (topic,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return jsonify({"memory": result[0] if result else "No memory found"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint to keep database awake
@app.route("/ping-db", methods=["GET"])
def ping_db():
    error = verify_api_key()
    if error: return error  # Deny request if API key is wrong

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "Database is awake"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Initialize database (if needed)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
