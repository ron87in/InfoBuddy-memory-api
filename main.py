from flask import Flask, request, jsonify
import psycopg2
import os
from flasgger import Swagger
from flask_cors import CORS
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
API_KEY = os.getenv("API_KEY")

app = Flask(__name__)
CORS(app)
Swagger(app)

# Ensure DB connection
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

# Ensure table exists
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            topic TEXT PRIMARY KEY,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    cursor.close()
    conn.close()

init_db()  # Initialize DB on startup

# Secure function to check API key
def check_api_key(req):
    provided_key = req.headers.get("X-API-KEY")
    return provided_key == API_KEY

# Route: Store memory
@app.route("/remember", methods=["POST"])
def remember():
    """
    Store or update a memory.
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            topic:
              type: string
              description: The topic of the memory.
            details:
              type: string
              description: The details of the memory.
    responses:
      200:
        description: Memory stored successfully.
      403:
        description: Unauthorized access.
      400:
        description: Invalid data.
    """
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    topic = data.get("topic", "").strip().lower()
    details = data.get("details", "").strip()

    if not topic or not details:
        return jsonify({"error": "Invalid data"}), 400

    timestamp = datetime.utcnow()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO memory (topic, details, timestamp)
            VALUES (%s, %s, %s)
            ON CONFLICT (topic)
            DO UPDATE SET details = EXCLUDED.details, timestamp = EXCLUDED.timestamp;
            """,
            (topic, details, timestamp)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": f"Memory stored: '{topic}' -> '{details}'", "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route: Retrieve memory
@app.route("/recall", methods=["GET"])
def recall():
    """
    Recall a stored memory.
    ---
    parameters:
      - name: topic
        in: query
        type: string
        required: true
        description: The topic of the memory to recall.
    responses:
      200:
        description: Memory retrieved successfully.
      403:
        description: Unauthorized access.
      400:
        description: No topic provided.
      404:
        description: No memory found.
    """
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    topic = request.args.get("topic", "").strip().lower()
    if not topic:
        return jsonify({"error": "No topic provided"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT details, timestamp FROM memory WHERE topic = %s;", (topic,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            details, timestamp = result
            return jsonify({
                "memory": details,
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
            }), 200
        else:
            return jsonify({"memory": "No memory found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route: Keep database alive (for UptimeRobot)
@app.route("/ping-db", methods=["GET"])
def ping_db():
    """
    Health check endpoint for database connectivity.
    ---
    responses:
      200:
        description: Database connection successful.
      500:
        description: Database connection failed.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        cursor.close()
        conn.close()
        return jsonify({"status": "Database is active"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Start Flask app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)