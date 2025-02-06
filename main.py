from flask import Flask, request, jsonify
import psycopg2
import os
import datetime
import pytz
from dateutil import parser, relativedelta

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

# Set default timezone to Central Time
CENTRAL_TZ = pytz.timezone("America/Chicago")

# Endpoint to save memory with timestamp
@app.route("/remember", methods=["POST"])
def remember():
    error = verify_api_key()
    if error: return error  # Deny request if API key is wrong

    data = request.json
    topic = data.get("topic")
    details = data.get("details")
    timestamp_utc = datetime.datetime.utcnow().replace(tzinfo=pytz.utc).isoformat()
    timestamp_central = timestamp_utc.astimezone(CENTRAL_TZ).isoformat()

    print(f"DEBUG: Saving memory - topic={topic}, details={details}, timestamp={timestamp_utc}")  # Debug log

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE memory ADD COLUMN IF NOT EXISTS timestamp TIMESTAMP DEFAULT NOW();")
        cursor.execute(
            "INSERT INTO memory (topic, details, timestamp) VALUES (%s, %s, %s) "
            "ON CONFLICT (topic) DO UPDATE SET details = EXCLUDED.details, timestamp = NOW();",
            (topic, details, timestamp_utc)
        )
        conn.commit()
        cursor.close()
        conn.close()
        print(f"DEBUG: Memory successfully saved - {topic}, {timestamp_utc}")
        return jsonify({"status": "Memory saved", "timestamp": timestamp_utc}), 200
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Endpoint to recall memory with timestamp
@app.route("/recall", methods=["GET"])
def recall():
    error = verify_api_key()
    if error: return error  # Deny request if API key is wrong

    topic = request.args.get("topic")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT details, timestamp FROM memory WHERE topic = %s", (topic,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        print(f"DEBUG: Retrieved memory from DB -> {result}")

        if result:
            details, timestamp_utc = result
            if timestamp_utc:
                memory_time_utc = parser.parse(str(timestamp_utc)).replace(tzinfo=pytz.utc)
                memory_time_central = memory_time_utc.astimezone(CENTRAL_TZ)
                time_difference = relativedelta.relativedelta(
                    datetime.datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(CENTRAL_TZ), 
                    memory_time_central
                )
                time_ago = f"{time_difference.years} years, {time_difference.months} months, and {time_difference.days} days ago"
                formatted_memory = f"{details} (Recorded {time_ago} at {memory_time_central.strftime('%Y-%m-%d %I:%M %p %Z')})"
            else:
                formatted_memory = f"{details} (No timestamp available)"
            return jsonify({"memory": formatted_memory}), 200
        else:
            return jsonify({"memory": "No memory found"}), 200
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Debugging API to check database schema and latest entries
@app.route("/debug-db", methods=["GET"])
def debug_db():
    error = verify_api_key()
    if error: return error  # Deny request if API key is wrong

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if timestamp column exists
        cursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'memory';")
        columns = cursor.fetchall()

        # Check the latest memories
        cursor.execute("SELECT * FROM memory ORDER BY timestamp DESC LIMIT 5;")
        recent_memories = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "columns": columns,
            "recent_memories": recent_memories
        }), 200
    except Exception as e:
        print(f"ERROR: {str(e)}")
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
        print(f"ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Initialize database (if needed)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
