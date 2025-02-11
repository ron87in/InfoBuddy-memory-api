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
    logging.error("❌ ERROR: API Key not found.")

if DATABASE_URL:
    logging.info("✅ Database URL successfully loaded.")
else:
    logging.error("❌ ERROR: Database URL not found.")

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

def safe_init_db():
    """
    Safely create the 'memory' table if it doesn't exist.
    This version preserves existing data.
    """
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()

            # Check if table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'memory'
                );
            """)
            table_exists = cursor.fetchone()[0]

            if not table_exists:
                logging.info("Creating memory table for the first time...")
                cursor.execute("""
                    CREATE TABLE memory (
                        id SERIAL PRIMARY KEY,
                        topic TEXT NOT NULL,
                        details JSONB,
                        timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.commit()
                logging.info("✅ Memory table created successfully.")
            else:
                logging.info("✅ Memory table already exists, preserving data.")

            # Create indexes for better search performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_topic ON memory (topic);
                CREATE INDEX IF NOT EXISTS idx_memory_timestamp ON memory (timestamp);
            """)
            conn.commit()

            # Log current record count
            cursor.execute("SELECT COUNT(*) FROM memory")
            count = cursor.fetchone()[0]
            logging.info(f"📊 Current record count in memory table: {count}")

        except Exception as e:
            logging.error(f"❌ Error during database initialization: {str(e)}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
    else:
        logging.error("❌ ERROR: Database initialization failed - couldn't connect.")

###############################################################################
#                             BACKUP FUNCTIONS                                #
###############################################################################

def backup_database():
    """Create a JSON backup of all memories."""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT topic, details, timestamp 
                FROM memory 
                ORDER BY timestamp DESC
            """)
            memories = cursor.fetchall()

            backup_data = []
            for memory in memories:
                backup_data.append({
                    "topic": memory[0],
                    "details": memory[1],
                    "timestamp": memory[2].isoformat()
                })

            # Create backups directory if it doesn't exist
            os.makedirs("backups", exist_ok=True)

            # Create backup file with timestamp
            backup_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"backups/memory_backup_{backup_time}.json"

            with open(backup_file, "w") as f:
                json.dump(backup_data, f, indent=2)

            logging.info(f"✅ Backup created successfully: {backup_file}")
            return backup_file

        except Exception as e:
            logging.error(f"❌ Backup failed: {str(e)}")
        finally:
            cursor.close()
            conn.close()
    return None

def restore_from_backup(backup_file):
    """Restore memories from a backup file."""
    if not os.path.exists(backup_file):
        logging.error("❌ Backup file not found")
        return False

    conn = get_db_connection()
    if not conn:
        return False

    try:
        with open(backup_file, 'r') as f:
            memories = json.load(f)

        cursor = conn.cursor()
        for memory in memories:
            cursor.execute(
                """
                INSERT INTO memory (topic, details, timestamp)
                VALUES (%s, %s::jsonb, %s)
                """,
                (memory["topic"], json.dumps(memory["details"]), memory["timestamp"])
            )

        conn.commit()
        logging.info(f"✅ Successfully restored {len(memories)} memories from backup")
        return True

    except Exception as e:
        logging.error(f"❌ Restore failed: {str(e)}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

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
            """,
            (topic, details_json, timestamp)
        )
        conn.commit()
        cursor.close()
        conn.close()

        # Create backup after successful insert
        backup_database()

        return jsonify({"message": f"Memory stored: '{topic}'"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

###############################################################################
#                             /recall-or-search                               #
###############################################################################

@app.route("/recall-or-search", methods=["GET"])
def recall_or_search():
    """Retrieve all memories related to a topic, searching across topics and details."""
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    topic = request.args.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "No topic provided"}), 400

    logging.info(f"🔍 Searching for topic: {topic}")

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        cursor = conn.cursor()

        # First, check total records
        cursor.execute("SELECT COUNT(*) FROM memory")
        total_count = cursor.fetchone()[0]
        logging.info(f"📊 Total records in database: {total_count}")

        # Improved search query with better JSONB handling
        cursor.execute("""
            SELECT topic, details, timestamp 
            FROM memory 
            WHERE topic ILIKE %s 
               OR details->>'text' ILIKE %s
               OR details::text ILIKE %s
            ORDER BY timestamp DESC;
        """, (f"%{topic}%", f"%{topic}%", f"%{topic}%"))

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
#                             RESTORE ENDPOINT                                #
###############################################################################

@app.route("/restore", methods=["POST"])
def restore():
    """Restore memories from a backup file."""
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    if not data or "backup_file" not in data:
        return jsonify({"error": "No backup file specified"}), 400

    success = restore_from_backup(data["backup_file"])
    if success:
        return jsonify({"message": "Memories restored successfully"}), 200
    else:
        return jsonify({"error": "Failed to restore memories"}), 500


###############################################################################
#                             DELETE ENDPOINT                                 #
###############################################################################

@app.route("/delete", methods=["DELETE"])
def delete_memory():
    """Delete a specific memory by topic and timestamp."""
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        topic = data.get("topic")
        timestamp = data.get("timestamp")

        if not topic or not timestamp:
            return jsonify({"error": "Missing topic or timestamp"}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = conn.cursor()

        # Create backup before deletion
        backup_database()

        cursor.execute(
            """
            DELETE FROM memory 
            WHERE topic = %s AND timestamp = %s::timestamptz
            RETURNING id
            """,
            (topic, timestamp)
        )

        deleted = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        if deleted:
            return jsonify({"message": f"Memory deleted: '{topic}'"}), 200
        else:
            return jsonify({"error": "Memory not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500

###############################################################################
#                             MAIN APP RUN                                    #
###############################################################################

if __name__ == "__main__":
    safe_init_db()  # Initialize database safely
    app.run(host="0.0.0.0", port=10000)