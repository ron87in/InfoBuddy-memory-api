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
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Define valid memory categories with descriptions
class MemoryCategory(Enum):
    WORK_AND_MILITARY = {
        'value': 'work_and_military',
        'description': 'Army service, workplace experiences, career decisions, professional ethics'
    }
    PERSONAL_GROWTH = {
        'value': 'personal_growth',
        'description': 'Self-improvement, emotional processing, mental health, morals & ideals'
    }
    ADVENTURE_AND_TRAVEL = {
        'value': 'adventure_and_travel',
        'description': 'Moving & relocation, travel experiences, spontaneous experiences, long-term travel goals'
    }
    HOBBIES_AND_INTERESTS = {
        'value': 'hobbies_and_interests',
        'description': 'Creative activities, entertainment, fitness & sports, personal projects'
    }
    ROMANTIC_RELATIONSHIPS = {
        'value': 'romantic_relationships',
        'description': 'Dating experiences, relationship struggles, love & attraction'
    }
    FRIENDS_AND_FAMILY = {
        'value': 'friends_and_family',
        'description': 'Current relationships, family interactions, social struggles'
    }
    UPBRINGING_AND_LORE = {
        'value': 'upbringing_and_lore',
        'description': 'Childhood memories, past experiences, family history'
    }
    INFOBUDDY_RELATIONSHIP = {
        'value': 'infobuddy_relationship',
        'description': 'Conversations about AI companionship, memory continuity, friendship aspect'
    }
    INFOBUDDY_TECHNICAL = {
        'value': 'infobuddy_technical',
        'description': 'Software development, feature planning, system improvements, future AI vision'
    }
    MISCELLANEOUS = {
        'value': 'miscellaneous',
        'description': 'Anything that doesn\'t fit neatly into another category'
    }

    @classmethod
    def get_values(cls):
        return [member.value['value'] for member in cls]

    @classmethod
    def get_descriptions(cls):
        return {member.value['value']: member.value['description'] for member in cls}

# Debugging confirmation
if API_KEY:
    logging.debug("✅ API Key loaded.")
else:
    logging.debug("❌ No API Key found.")

if DATABASE_URL:
    logging.debug("✅ Database URL loaded.")
else:
    logging.debug("❌ ERROR: Database URL not found.")

app = Flask(__name__)
CORS(app)
Swagger(app)

###############################################################################
#                             DB CONNECTION                                    #
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
                # First ensure the enum type exists
                cursor.execute("""
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'memory_category') THEN
                            CREATE TYPE memory_category AS ENUM (
                                'work_and_military',
                                'personal_growth',
                                'adventure_and_travel',
                                'hobbies_and_interests',
                                'romantic_relationships',
                                'friends_and_family',
                                'upbringing_and_lore',
                                'infobuddy_relationship',
                                'infobuddy_technical',
                                'miscellaneous'
                            );
                        END IF;
                    END $$;
                """)

                cursor.execute("""
                    CREATE TABLE memory (
                        id SERIAL PRIMARY KEY,
                        title TEXT NOT NULL,
                        details JSONB,
                        categories memory_category[] NOT NULL,
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
                CREATE INDEX IF NOT EXISTS idx_memory_categories ON memory USING gin (categories);
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
#                             BACKUP FUNCTIONS                                 #
###############################################################################

def backup_database():
    """Create a JSON backup of all memories."""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT title, details, categories, timestamp 
                FROM memory 
                ORDER BY timestamp DESC
            """)
            memories = cursor.fetchall()

            backup_data = []
            for memory in memories:
                backup_data.append({
                    "title": memory[0],
                    "details": memory[1],
                    "categories": memory[2],
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
#                         SECURITY FUNCTION                                    #
###############################################################################

def check_api_key(req):
    """
    Check that the request has a valid API key.
    Looks first for a Bearer token in the Authorization header,
    then for an X-API-KEY header,
    and finally for an 'api_key' query parameter.
    """
    token = None

    # 1. Check Authorization header (expecting "Bearer <token>")
    auth_header = req.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()

    # 2. Fallback: Check X-API-KEY header
    if not token:
        token = req.headers.get("X-API-KEY")

    # 3. Fallback: Check query parameter (e.g., ?api_key=YOUR_API_KEY)
    if not token:
        token = req.args.get("api_key")

    logging.debug("Token from request: %r", token)

    if not token:
        logging.warning("🚨 Missing API key in request (headers or query parameter).")
        return False

    expected_key = API_KEY.strip() if API_KEY else None
    logging.debug("Expected API key: %r", expected_key)

    if token != expected_key:
        logging.warning("🚨 API key mismatch: provided token does not match expected key.")
        return False

    return True


###############################################################################
#                             MEMORY HANDLERS                                  #
###############################################################################

@app.route("/remember", methods=["POST"])
def remember():
    """Store a memory with title, details, and multiple categories."""
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        title = str(data.get("title", "")).strip()
        details = str(data.get("details", "")).strip()
        categories = data.get("categories", [])

        if not title or not details or not categories:
            return jsonify({"error": "Missing title, details, or categories"}), 400

        if not isinstance(categories, list):
            return jsonify({"error": "Categories must be provided as a list"}), 400

        # Validate categories
        valid_categories = MemoryCategory.get_values()
        categories = [cat.strip() for cat in categories]
        invalid_categories = [cat for cat in categories if cat not in valid_categories]
        if invalid_categories:
            return jsonify({
                "error": f"Invalid categories: {invalid_categories}. Must be one or more of: {valid_categories}"
            }), 400

        logging.info(f"Attempting to store memory - Title: {title}, Categories: {categories}")

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
            INSERT INTO memory (title, details, categories, timestamp)
            VALUES (%s, %s::jsonb, %s::memory_category[], %s)
            """,
            (title, details_json, categories, timestamp)
        )
        conn.commit()
        cursor.close()
        conn.close()

        # Create backup after successful insert
        backup_database()

        return jsonify({
            "message": f"Memory stored: '{title}'",
            "categories": categories
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/recall-or-search", methods=["GET"])
def recall_or_search():
    """Retrieve memories by title, details, or categories, converting timestamps to Chicago time."""
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    search_term = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        cursor = conn.cursor()

        if not search_term and not category:
            # Return recent memories if no search parameters
            cursor.execute("""
                SELECT title, details, categories, timestamp 
                FROM memory 
                ORDER BY timestamp DESC
                LIMIT 10;
            """)
        else:
            params = []
            conditions = []

            if search_term:
                conditions.append("(title ILIKE %s OR details->>'text' ILIKE %s)")
                params.extend([f"%{search_term}%", f"%{search_term}%"])

            if category:
                conditions.append("%s = ANY(categories)")
                params.append(category)

            query = """
                SELECT title, details, categories, timestamp 
                FROM memory 
                WHERE """ + " OR ".join(conditions) + """
                ORDER BY timestamp DESC;
            """
            cursor.execute(query, params)

        memories = []
        chicago_tz = pytz.timezone("America/Chicago")
        for row in cursor.fetchall():
            details = row[1]
            if isinstance(details, str):
                details = json.loads(details)

            # Convert timestamp to Chicago time
            timestamp_chicago = row[3].astimezone(chicago_tz) if row[3] else None

            memories.append({
                "title": row[0],
                "details": details["text"] if isinstance(details, dict) and "text" in details else str(details),
                "categories": row[2],
                "timestamp": timestamp_chicago.isoformat() if timestamp_chicago else None
            })

        cursor.close()
        conn.close()

        if not memories:
            return jsonify({
                "message": "No memories found matching your search.",
                "suggestion": "Try a different search term or category."
            }), 404

        return jsonify({
            "memories": memories,
            "total_found": len(memories)
        }), 200

    except Exception as e:
        logging.error(f"❌ ERROR in /recall-or-search: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/delete", methods=["DELETE"])
def delete_memory():
    """Delete a specific memory by title. If multiple exist, deletes the most recent one."""
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    title = request.args.get("title")
    if not title:
        return jsonify({"error": "Missing title"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    cursor = conn.cursor()

    # Look up the most recent memory with the given title
    cursor.execute("""
        SELECT timestamp FROM memory 
        WHERE title = %s 
        ORDER BY timestamp DESC 
        LIMIT 1
    """, (title,))
    result = cursor.fetchone()
    if not result:
        cursor.close()
        conn.close()
        return jsonify({"error": "Memory not found"}), 404

    stored_timestamp = result[0]

    cursor.execute("""
        DELETE FROM memory 
        WHERE title = %s AND timestamp = %s::timestamptz
    """, (title, stored_timestamp))
    deleted = cursor.rowcount > 0
    conn.commit()
    cursor.close()
    conn.close()

    if deleted:
        return jsonify({"message": f"Memory deleted: '{title}'"}), 200
    else:
        return jsonify({"error": "Memory not found"}), 404

###############################################################################
#                             MAIN APP RUN                                     #
###############################################################################

if __name__ == "__main__":
    safe_init_db()  # Initialize database safely
    app.run(host="0.0.0.0", port=10000)
