from flask import Flask, request, jsonify
import psycopg2
import os
import datetime
import pytz
import json
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

# Middleware to check API Key, supporting both X-API-KEY and Authorization Bearer
def verify_api_key():
    key = request.headers.get("X-API-KEY") or request.headers.get("Authorization")

    # If Authorization header is used, extract Bearer token
    if key and key.startswith("Bearer "):
        key = key.split(" ")[1]

    if key != API_KEY:
        print(f"DEBUG: Unauthorized access attempt.")
        print(f"DEBUG: Headers Received -> {dict(request.headers)}")  # Log full headers for debugging
        return jsonify({"error": "Unauthorized access"}), 403

# Log every incoming request
@app.before_request
def log_request_info():
    print(f"DEBUG: Received {request.method} request to {request.path}")
    if request.args:
        print(f"DEBUG: Query Params -> {request.args}")
    if request.data:
        print(f"DEBUG: Raw Data Payload -> {request.data}")
    print(f"DEBUG: Headers -> {dict(request.headers)}")

# Set default timezone to Central Time
CENTRAL_TZ = pytz.timezone("America/Chicago")

# Endpoint to save memory with timestamp
@app.route("/remember", methods=["POST"])
def remember():
    error = verify_api_key()
    if error: return error  # Deny request if API key is wrong

    print(f"DEBUG: Received POST /remember request")
    print(f"DEBUG: Headers -> {dict(request.headers)}")
    print(f"DEBUG: Content-Type Received -> {request.headers.get('Content-Type')}")

    # Manually parse JSON from request body
    try:
        data = json.loads(request.data.decode('utf-8'))  # Decode raw body manually
        print(f"DEBUG: Parsed JSON Payload -> {data}")
    except Exception as e:
        print(f"ERROR: Failed to parse JSON - {str(e)}")
        return jsonify({"error": "Invalid JSON format"}), 400

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
        print(f"ERROR: Exception in /remember -> {str(e)}")
        return jsonify({"error": str(e)}), 500

# Endpoint to recall memory with timestamp
@app.route("/recall", methods=["GET"])
def recall():
    error = verify_api_key()
    if error: return error  # Deny request if API key is wrong

    print(f"DEBUG: Received GET /recall request")
    print(f"DEBUG: Headers -> {dict(request.headers)}")
    print(f"DEBUG: Query Params -> {request.args}")

    topic = request.args.get("topic")
    if not topic:
        print("ERROR: Missing 'topic' parameter in /recall")
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
    list_routes()
    app.run(host="0.0.0.0", port=8080)
