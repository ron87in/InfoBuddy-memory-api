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
from enum import Enum

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

# Define valid memory categories
class MemoryCategory(Enum):
    WORK_AND_MILITARY = 'work_and_military'
    PERSONAL_GROWTH = 'personal_growth'
    ADVENTURE_AND_TRAVEL = 'adventure_and_travel'
    HOBBIES_AND_INTERESTS = 'hobbies_and_interests'
    ROMANTIC_RELATIONSHIPS = 'romantic_relationships'
    FRIENDS_AND_FAMILY = 'friends_and_family'
    UPBRINGING_AND_LORE = 'upbringing_and_lore'
    INFOBUDDY_RELATIONSHIP = 'infobuddy_relationship'
    INFOBUDDY_TECHNICAL = 'infobuddy_technical'
    MISCELLANEOUS = 'miscellaneous'

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
                        title TEXT NOT NULL,
                        details JSONB,
                        category memory_category NOT NULL,
                        timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.commit()
                logging.info("✅ Memory table created successfully.")
            else:
                logging.info("✅ Memory table already exists, preserving data.")

            # Create indexes for better search performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_title ON memory (title);
                CREATE INDEX IF NOT EXISTS idx_memory_category ON memory (category);
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
                SELECT title, details, category, timestamp 
                FROM memory 
                ORDER BY timestamp DESC
            """)
            memories = cursor.fetchall()

            backup_data = []
            for memory in memories:
                backup_data.append({
                    "title": memory[0],
                    "details": memory[1],
                    "category": memory[2],
                    "timestamp": memory[3].isoformat()
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
#                             MEMORY HANDLERS                                #
###############################################################################

@app.route("/remember", methods=["POST"])
def remember():
    """Store a memory with title, details, and category."""
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        title = str(data.get("title", "")).strip()
        details = str(data.get("details", "")).strip()
        category = data.get("category", "").strip()

        if not title or not details or not category:
            return jsonify({"error": "Missing title, details, or category"}), 400

        # Validate category
        try:
            category = MemoryCategory(category).value
        except ValueError:
            return jsonify({"error": f"Invalid category. Must be one of: {[c.value for c in MemoryCategory]}"}), 400

        logging.info(f"Attempting to store memory - Title: {title}, Category: {category}")

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
            INSERT INTO memory (title, details, category, timestamp)
            VALUES (%s, %s::jsonb, %s::memory_category, %s)
            """,
            (title, details_json, category, timestamp)
        )
        conn.commit()
        cursor.close()
        conn.close()

        # Create backup after successful insert
        backup_database()

        return jsonify({
            "message": f"Memory stored: '{title}'",
            "category": category
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/recall-or-search", methods=["GET"])
def recall_or_search():
    """Retrieve memories by title, details, or category."""
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    search_term = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()

    if not search_term and not category:
        return jsonify({"error": "No search term or category provided"}), 400

    if category:
        try:
            category = MemoryCategory(category).value
        except ValueError:
            return jsonify({"error": f"Invalid category. Must be one of: {[c.value for c in MemoryCategory]}"}), 400

    logging.info(f"🔍 Searching - Term: {search_term}, Category: {category}")

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        cursor = conn.cursor()

        # Build search query based on provided parameters
        query_parts = []
        query_params = []

        if search_term:
            query_parts.extend([
                "title ILIKE %s",
                "details->>'text' ILIKE %s"
            ])
            query_params.extend([f"%{search_term}%", f"%{search_term}%"])

        if category:
            query_parts.append("category = %s::memory_category")
            query_params.append(category)

        query = f"""
            SELECT title, details, category, timestamp 
            FROM memory 
            WHERE {' OR '.join(query_parts) if search_term else query_parts[0]}
            ORDER BY timestamp DESC;
        """

        cursor.execute(query, query_params)
        search_results = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) FROM memory")
        total_count = cursor.fetchone()[0]
        logging.info(f"📊 Found {len(search_results)} results out of {total_count} total memories")

        cursor.close()
        conn.close()

        if not search_results:
            if total_count == 0:
                return jsonify({"error": "Database is empty"}), 404
            return jsonify({"error": f"No memories found matching search criteria"}), 404

        # Convert results into JSON format
        memories = []
        for row in search_results:
            try:
                details = row[1]
                if isinstance(details, str):
                    details = json.loads(details)

                memory = {
                    "title": row[0],
                    "details": details["text"] if isinstance(details, dict) and "text" in details else str(details),
                    "category": row[2],
                    "timestamp": row[3].isoformat() if row[3] else None
                }
                memories.append(memory)
            except Exception as e:
                logging.error(f"Error parsing memory: {e}")
                continue

        return jsonify({"memories": memories}), 200

    except Exception as e:
        logging.error(f"❌ ERROR in /recall-or-search: {str(e)}")
        return jsonify({"error": str(e)}), 500

###############################################################################
#                             DELETE ENDPOINT                                 #
###############################################################################

@app.route("/delete", methods=["DELETE"])
def delete_memory():
    """Delete a specific memory by title and timestamp."""
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    try:
        title = request.args.get("title")
        timestamp = request.args.get("timestamp")

        if not title or not timestamp:
            return jsonify({"error": "Missing title or timestamp"}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = conn.cursor()

        # Create backup before deletion
        backup_database()

        cursor.execute(
            """
            DELETE FROM memory 
            WHERE title = %s AND timestamp = %s::timestamptz
            RETURNING id
            """,
            (title, timestamp)
        )

        deleted = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        if deleted:
            return jsonify({"message": f"Memory deleted: '{title}'"}), 200
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