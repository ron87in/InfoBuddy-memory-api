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

    print(f"DEBUG: Received Headers -> {dict(request.headers)}")
    print(f"DEBUG: Content-Type Received -> {request.headers.get('Content-Type')}")

    if not request.is_json:
        return jsonify({
            "error": "Request must be JSON",
            "received_content_type": request.headers.get("Content-Type")
        }), 415

    data = request.json
    topic = data.get("topic")
    details = data.get("details")
    timestamp_utc = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)

    print(f"DEBUG: Storing memory - Topic: {topic}, Details: {details}, Timestamp: {timestamp_utc}")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO memory (topic, details, timestamp) 
            VALUES (%s, %s, NOW()) 
            ON CONFLICT (topic) 
            DO UPDATE SET details = EXCLUDED.details, timestamp = NOW();
            """,
            (topic, details)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "Memory saved"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint to recall memory with timestamp
@app.route("/recall", methods=["GET"])
def recall():
    error = verify_api_key()
    if error: return error  # Deny request if API key is wrong

    print(f"DEBUG: Recall request received - Raw Query Params -> {request.args}")

    topic = request.args.get("topic")
    if not topic:
        return jsonify({
            "error": "Missing 'topic' query parameter",
            "received_query_params": dict(request.args)
        }), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT details, timestamp FROM memory WHERE topic = %s", (topic,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            details, timestamp_utc = result
            return jsonify({
                "memory": details,
                "timestamp": timestamp_utc.isoformat() if timestamp_utc else "No timestamp available"
            }), 200
        else:
            return jsonify({"memory": "No memory found"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Function to list all registered routes
def list_routes():
    for rule in app.url_map.iter_rules():
        print(f"DEBUG: Registered route -> {rule}")

# Initialize database and check routes before running the app
if __name__ == "__main__":
    list_routes()
    app.run(host="0.0.0.0", port=8080)
