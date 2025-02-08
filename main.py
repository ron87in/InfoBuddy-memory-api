from flask import Flask, request, jsonify
import os
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Retrieve API key from environment variables
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("ERROR: Missing API_KEY in environment variables.")

# Database connection setup
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("ERROR: Missing DATABASE_URL in environment variables.")

# Connect to PostgreSQL
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

@app.before_request
def validate_api_key():
    """ Validate API Key for every request """
    api_key = request.headers.get("X-Api-Key") or request.headers.get("x-api-key")

    if not api_key:
        print("DEBUG: ❌ No API Key provided!")
        return jsonify({"error": "Unauthorized - Missing API Key"}), 403

    if api_key.startswith("your"):
        print("DEBUG: ❌ Placeholder API key detected! ChatGPT might not be storing the real key.")
        return jsonify({"error": "Unauthorized - Invalid API Key"}), 403

    if api_key != API_KEY:
        print("DEBUG: ❌ Unauthorized request - Invalid API Key")
        return jsonify({"error": "Unauthorized - Invalid API Key"}), 403

    # Masked log for security (prints only last 4 characters)
    print(f"DEBUG: ✅ API Key received (ends with: {api_key[-4:]})")

@app.route("/remember", methods=["POST"])
def remember():
    """ Store a memory in the database """
    try:
        data = request.get_json()
        topic = data.get("topic")
        details = data.get("details")

        if not topic or not details:
            return jsonify({"error": "Missing required fields"}), 400

        timestamp = datetime.utcnow()

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO memories (topic, details, timestamp) VALUES (%s, %s, %s)",
                    (topic, details, timestamp))
        conn.commit()
        cur.close()
        conn.close()

        print(f"DEBUG: ✅ Memory stored - Topic: {topic}, Timestamp: {timestamp}")
        return jsonify({"message": "Memory saved successfully"}), 200

    except Exception as e:
        print(f"ERROR: ❌ Failed to save memory: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

@app.route("/recall", methods=["GET"])
def recall():
    """ Retrieve a memory by topic """
    try:
        topic = request.args.get("topic")
        if not topic:
            return jsonify({"error": "Missing topic parameter"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT details, timestamp FROM memories WHERE topic = %s ORDER BY timestamp DESC LIMIT 1", (topic,))
        result = cur.fetchone()
        cur.close()
        conn.close()

        if not result:
            return jsonify({"error": "Memory not found"}), 404

        details, timestamp = result
        print(f"DEBUG: ✅ Memory retrieved - Topic: {topic}, Timestamp: {timestamp}")
        return jsonify({"topic": topic, "details": details, "timestamp": timestamp}), 200

    except Exception as e:
        print(f"ERROR: ❌ Failed to retrieve memory: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

@app.route("/ping-db", methods=["HEAD", "GET"])
def ping_db():
    """ Check if the database is alive """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return jsonify({"message": "Database is alive"}), 200
    except Exception as e:
        print(f"ERROR: ❌ Database connection failed: {e}")
        return jsonify({"error": "Database connection failed"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
