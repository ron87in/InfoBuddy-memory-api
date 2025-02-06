from flask import Flask, request, jsonify
import psycopg2
import os
import datetime
import pytz
from dateutil import parser, relativedelta

app = Flask(__name__)

# Retrieve API Key from environment variable
API_KEY = os.getenv("API_KEY")
if API_KEY:
    print("DEBUG: API_KEY found.")
else:
    print("DEBUG: API_KEY not found!")

# Database connection function
def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# Ensure the memory table has a timestamp column
def ensure_timestamp_column():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the column exists
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'memory' AND column_name = 'timestamp';
        """)
        column_exists = cursor.fetchone()

        if not column_exists:
            print("DEBUG: Adding missing timestamp column...")
            cursor.execute("ALTER TABLE memory ADD COLUMN timestamp TIMESTAMP DEFAULT NOW();")
            conn.commit()
            print("DEBUG: Timestamp column successfully added.")

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"ERROR: Could not ensure timestamp column exists: {e}")

# Middleware to check API Key
def verify_api_key():
    key = request.headers.get("X-API-KEY")
    print(f"DEBUG: Checking API Key. Received -> {key}")

    if key != API_KEY:
        print("DEBUG: Unauthorized access detected.")
        return jsonify({"error": "Unauthorized access"}), 403

# Log every incoming request
@app.before_request
def log_request_info():
    print(f"DEBUG: Received {request.method} request to {request.path}")
    if request.args:
        print(f"DEBUG: Query Params -> {request.args}")
    if request.json:
        print(f"DEBUG: JSON Payload -> {request.json}")
    print(f"DEBUG: Headers -> {dict(request.headers)}")

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
    timestamp_utc = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)

    print(f"DEBUG: Attempting to store memory - topic={topic}, details={details}, timestamp={timestamp_utc}")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert the memory with timestamp
        cursor.execute(
            """
            INSERT INTO memory (topic, details, timestamp) 
            VALUES (%s, %s, %s) 
            ON CONFLICT (topic) 
            DO UPDATE SET details = EXCLUDED.details, timestamp = NOW();
            """,
            (topic, details, timestamp_utc)
        )

        conn.commit()
        cursor.close()
        conn.close()

        print(f"DEBUG: Successfully stored memory - topic={topic}, timestamp={timestamp_utc}")
        return jsonify({"status": "Memory saved", "timestamp": timestamp_utc.isoformat()}), 200

    except Exception as e:
        print(f"ERROR: Exception in /remember -> {str(e)}")
        return jsonify({"error": str(e)}), 500

# Endpoint to recall memory with timestamp
@app.route("/recall", methods=["GET"])
def recall():
    error = verify_api_key()
    if error:
        print("DEBUG: API Key check failed in /recall")
        return error  # Deny request if API key is wrong

    topic = request.args.get("topic")
    print(f"DEBUG: Looking for memory with topic '{topic}'")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT details, timestamp FROM memory WHERE topic = %s", (topic,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        print(f"DEBUG: Retrieved memory -> {result}")

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

            print(f"DEBUG: Formatted memory response -> {formatted_memory}")
            return jsonify({"memory": formatted_memory}), 200
        else:
            print("DEBUG: No memory found for topic")
            return jsonify({"memory": "No memory found"}), 200
    except Exception as e:
        print(f"ERROR: Exception in /recall -> {str(e)}")
        return jsonify({"error": str(e)}), 500

# Function to list all registered routes
def list_routes():
    for rule in app.url_map.iter_rules():
        print(f"DEBUG: Registered route -> {rule}")

# Initialize database and check routes before running the app
if __name__ == "__main__":
    ensure_timestamp_column()
    list_routes()
    app.run(host="0.0.0.0", port=8080)
