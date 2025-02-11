import os
import psycopg2
import logging
import json
import pytz
from flask import Flask, request, jsonify
from flask_cors import CORS
from flasgger import Swagger
from datetime import datetime
from dotenv import load_dotenv

###############################################################################
#                             ENV & APP SETUP                                  #
###############################################################################

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
API_KEY = os.getenv("API_KEY")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Debugging confirmation
if API_KEY:
    logging.info("✅ API Key successfully loaded.")
else:
    logging.info("❌ ERROR: API Key not found.")

if DATABASE_URL:
    logging.info("✅ Database URL successfully loaded.")
else:
    logging.info("❌ ERROR: Database URL not found.")

app = Flask(__name__)
CORS(app)
Swagger(app)

###############################################################################
#                             DB CONNECTION                                   #
###############################################################################

def get_db_connection():
    """Establish a connection to the PostgreSQL database."""
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logging.error(f"❌ Database Connection Error: {str(e)}")
        return None

###############################################################################
#                             INIT DB                                         #
###############################################################################

def init_db():
    """
    Create the 'memory' table if it doesn't exist,
    with columns: topic (TEXT), details (JSONB), timestamp (TIMESTAMPTZ).
    """
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id SERIAL PRIMARY KEY,
                topic TEXT,
                details JSONB,
                timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cursor.close()
        conn.close()
        logging.info("✅ Database initialized successfully.")
    else:
        logging.error("❌ ERROR: Database initialization failed.")

init_db()

###############################################################################
#                             CHECK API KEY                                   #
###############################################################################

def check_api_key(req):
    """Ensure the request has a valid API key."""
    provided_key = req.headers.get("X-API-KEY")
    if not API_KEY:
        logging.error("❌ ERROR: API Key is missing.")
        return False
    if provided_key != API_KEY:
        logging.warning("🚨 API KEY MISMATCH - Unauthorized request")
        return False
    return True

###############################################################################
#                             /remember                                       #
###############################################################################

@app.route("/remember", methods=["POST"])
def remember():
    """Store a memory in JSON format, ensuring all data is structured properly."""
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        topic = str(data.get("topic", "")).strip()
        details = str(data.get("details", "")).strip()

        if not topic or not details:
            return jsonify({"error": "Missing topic or details"}), 400

        logging.info(f"Attempting to store memory - Topic: {topic}, Details: {details}")

        chicago_tz = pytz.timezone("America/Chicago")
        timestamp = datetime.now(chicago_tz)

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        logging.info("Database connection successful")

        cursor = conn.cursor()

        # Ensure details is proper JSONB
        if isinstance(details, str):
            details_json = json.dumps({"text": details})
        elif isinstance(details, dict):
            details_json = json.dumps(details)
        else:
            return jsonify({"error": "Invalid details format"}), 400

        cursor.execute(
            """
            INSERT INTO memory (topic, details, timestamp)
            VALUES (%s, %s::jsonb, %s)
            RETURNING id;
            """,
            (topic, details_json, timestamp)
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": f"Memory stored: '{topic}'"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

###############################################################################
#                             /recall-or-search                               #
###############################################################################
@app.route("/recall-or-search", methods=["GET"])
def recall_or_search():
    """Retrieve **all** memories related to a topic, searching across topics and details."""
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    topic = request.args.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "No topic provided"}), 400

    logging.info(f"🔍 Searching for topic: {topic}")  # LOGGING SEARCH

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        cursor = conn.cursor()

        # 1) Search in topic & JSONB details
        # First, let's check if we have any records at all
        cursor.execute("SELECT COUNT(*) FROM memory")
        total_count = cursor.fetchone()[0]
        logging.info(f"📊 Total records in database: {total_count}")

        # Now perform the search
        cursor.execute("""
            SELECT topic, details, timestamp 
            FROM memory 
            WHERE topic ILIKE %s 
               OR details::text ILIKE %s
            ORDER BY timestamp DESC;
        """, (f"%{topic}%", f"%{topic}%"))

        search_results = cursor.fetchall()
        logging.info(f"🔍 Found {len(search_results)} results for topic: {topic}")

        cursor.close()
        conn.close()

        if not search_results:
            if total_count == 0:
                return jsonify({"error": "Database is empty"}), 404
            return jsonify({"error": f"No memories found matching '{topic}'"}), 404

        # Convert results into JSON format
        memories = []
        for row in search_results:
            try:
                details = row[1]
                if isinstance(details, str):
                    details = json.loads(details)
                
                memory = {
                    "topic": row[0] if row[0] else "[No Topic]",
                    "details": details["text"] if isinstance(details, dict) and "text" in details else str(details),
                    "timestamp": row[2].isoformat() if row[2] else None
                }
                memories.append(memory)
            except Exception as e:
                logging.error(f"Error parsing memory: {e}")
                continue

        logging.info(f"✅ Returning {len(memories)} memories for topic: {topic}")
        return jsonify({"memories": memories}), 200

    except Exception as e:
        logging.error(f"❌ ERROR in /recall-or-search: {str(e)}")
        return jsonify({"error": str(e)}), 500


###############################################################################
#                             MAIN APP RUN                                    #
###############################################################################

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
