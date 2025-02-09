import os
import psycopg2
from flask import Flask, request, jsonify
from flask_cors import CORS
from flasgger import Swagger
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()  # Ensures env vars load if running locally
DATABASE_URL = os.getenv("DATABASE_URL")
API_KEY = os.getenv("API_KEY")

# Debugging confirmation
if API_KEY:
    print("✅ API Key successfully loaded.")
else:
    print("❌ ERROR: API Key not found. Make sure it's set in Render.")

if DATABASE_URL:
    print("✅ Database URL successfully loaded.")
else:
    print("❌ ERROR: Database URL not found. Check Render settings.")

app = Flask(__name__)
CORS(app)
Swagger(app)

def get_db_connection():
    """Establish a connection to the PostgreSQL database."""
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"❌ Database Connection Error: {str(e)}")
        return None

# Ensure the memory table exists
def init_db():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                topic TEXT PRIMARY KEY,
                details TEXT,
                timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Database initialized successfully.")
    else:
        print("❌ ERROR: Database initialization failed.")

init_db()  # Initialize database at startup

def check_api_key(req):
    """Ensure the request has a valid API key."""
    provided_key = req.headers.get("X-API-KEY")

    if not API_KEY:
        print("❌ ERROR: API Key is missing from the environment.")
        return False

    if provided_key != API_KEY:
        print("🚨 API KEY MISMATCH - Unauthorized request")
        return False

    return True

@app.route("/remember", methods=["POST"])
def remember():
    """Store or update a memory by topic."""
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    # Remove .lower() so we preserve the topic’s original capitalization
    topic = data.get("topic", "").strip()  
    details = data.get("details", "").strip()

    if not topic or not details:
        return jsonify({"error": "Missing topic or details"}), 400

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO memory (topic, details, timestamp)
            VALUES (%s, %s, %s)
            ON CONFLICT (topic) DO UPDATE 
            SET details = EXCLUDED.details, timestamp = EXCLUDED.timestamp;
            """,
            (topic, details, datetime.utcnow())
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": f"Memory stored: '{topic}'"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/recall", methods=["GET"])
def recall():
    """Retrieve memory details by topic."""
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    # Remove .lower() on the input, but do a LOWER() match in the query.
    topic = request.args.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "No topic provided"}), 400

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = conn.cursor()
        # CASE-INSENSITIVE MATCH:
        cursor.execute(
            "SELECT details, timestamp FROM memory WHERE LOWER(topic) = LOWER(%s);",
            (topic,)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            return jsonify({"memory": result[0], "timestamp": result[1]}), 200
        else:
            return jsonify({"memory": "No memory found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/list-memories", methods=["GET"])
def list_memories():
    """Retrieve a list of all stored memories."""
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = conn.cursor()
        cursor.execute("SELECT topic, details, timestamp FROM memory ORDER BY timestamp DESC;")
        results = cursor.fetchall()
        cursor.close()
        conn.close()

        memories = [{"topic": row[0], "details": row[1], "timestamp": row[2]} for row in results]
        return jsonify({"memories": memories}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/ping-db", methods=["HEAD", "GET"])
def ping_db():
    """Ping the database to keep it alive."""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        cursor.close()
        conn.close()
        return jsonify({"status": "Database is active"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
