import os
import psycopg2
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from flasgger import Swagger
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
API_KEY = os.getenv("API_KEY")

# Debugging confirmation
if API_KEY:
    logging.info("✅ API Key successfully loaded.")
else:
    logging.info("❌ ERROR: API Key not found. Make sure it's set in Render.")

if DATABASE_URL:
    logging.info("✅ Database URL successfully loaded.")
else:
    logging.info("❌ ERROR: Database URL not found. Check Render settings.")

app = Flask(__name__)
CORS(app)
Swagger(app)

def get_db_connection():
    """Establish a connection to the PostgreSQL database."""
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logging.info(f"❌ Database Connection Error: {str(e)}")
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
        logging.info("✅ Database initialized successfully.")
    else:
        logging.info("❌ ERROR: Database initialization failed.")

init_db()

def check_api_key(req):
    """Ensure the request has a valid API key."""
    provided_key = req.headers.get("X-API-KEY")
    if not API_KEY:
        logging.info("❌ ERROR: API Key is missing from the environment.")
        return False
    if provided_key != API_KEY:
        logging.info("🚨 API KEY MISMATCH - Unauthorized request")
        return False
    return True

@app.route("/remember", methods=["POST"])
def remember():
    """
    Store or update a memory by topic (case-sensitive storage).
    Falls back to:
      - ON CONFLICT for updating existing topic
    """
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    topic = data.get("topic", "").strip()
    details = data.get("details", "").strip()

    if not topic or not details:
        return jsonify({"error": "Missing topic or details"}), 400

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = conn.cursor()

        # Insert or update the memory
        cursor.execute("""
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
    """
    Retrieve memory details by topic (exact match, ignoring case).
    Does NOT do fallback searching; if no match, returns 404.
    """
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    topic = request.args.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "No topic provided"}), 400

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = conn.cursor()
        # Case-insensitive exact match
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

@app.route("/recall-or-search", methods=["GET"])
def recall_or_search():
    """
    Tries exact match first (case-insensitive).
    If none, does a broad substring search across topic & details.
    """
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    topic = request.args.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "No topic provided"}), 400

    try:
        logging.info(f"🔎 Incoming request to /recall-or-search?topic={topic}")
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        cursor = conn.cursor()

        # 1) Exact match (case-insensitive)
        cursor.execute(
            "SELECT details, timestamp FROM memory WHERE LOWER(topic) = LOWER(%s);",
            (topic,)
        )
        exact_match = cursor.fetchone()
        logging.info(f"   • Exact match? {bool(exact_match)}")

        # 2) Fallback: search in both topic & details
        cursor.execute(
            """
            SELECT topic, details, timestamp
            FROM memory
            WHERE topic ILIKE %s
               OR details ILIKE %s
            ORDER BY timestamp DESC;
            """,
            (f"%{topic}%", f"%{topic}%")
        )
        search_results = cursor.fetchall()
        logging.info(f"   • Found {len(search_results)} search results for '{topic}'.")

        cursor.close()
        conn.close()

        response_data = {}

        if exact_match:
            response_data["exact_match"] = {
                "memory": exact_match[0],
                "timestamp": exact_match[1]
            }

        if search_results:
            # Convert to JSON-friendly list
            response_data["related_memories"] = [
                {
                    "topic": row[0],
                    "details": row[1],
                    "timestamp": row[2]
                }
                for row in search_results
            ]

        if not response_data:
            logging.info(f"🛑 No memory found for '{topic}' in topic or details. Returning 404.")
            return jsonify({"memory": "No memory found"}), 404

        # Return the combined data
        return jsonify(response_data), 200

    except Exception as e:
        logging.info(f"❌ ERROR in /recall-or-search: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/search", methods=["GET"])
def search_memory():
    """
    Search the memory database by substring in 'topic' OR 'details'.
    (Case-insensitive, returns all matches.)
    """
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "No search query provided"}), 400

    try:
        logging.info(f"🔎 Searching with query='{query}' in /search endpoint.")
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT topic, details, timestamp
            FROM memory
            WHERE topic ILIKE %s
               OR details ILIKE %s
            ORDER BY timestamp DESC;
            """,
            (f"%{query}%", f"%{query}%")
        )
        results = cursor.fetchall()
        logging.info(f"   • /search found {len(results)} results for '{query}'.")

        cursor.close()
        conn.close()

        memories = []
        for row in results:
            memories.append({
                "topic": row[0],
                "details": row[1],
                "timestamp": row[2]
            })

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
