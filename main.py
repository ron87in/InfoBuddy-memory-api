import os
import psycopg2
from flask import Flask, request, jsonify
from flask_cors import CORS
from flasgger import Swagger
from datetime import datetime

app = Flask(__name__)
CORS(app)
Swagger(app)

# Load environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
API_KEY = os.getenv("API_KEY")

def get_db_connection():
    """Establish a connection to the PostgreSQL database."""
    return psycopg2.connect(DATABASE_URL)

# Ensure the memory table exists
def init_db():
    conn = get_db_connection()
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

init_db()  # Initialize database at startup

def check_api_key(req):
    """Ensure the request has a valid API key."""
    provided_key = req.headers.get("X-API-KEY")
    if provided_key != API_KEY:
        return False
    return True

@app.route("/remember", methods=["POST"])
def remember():
    """Store or update a memory by topic.
    ---
    parameters:
      - name: X-API-KEY
        in: header
        type: string
        required: true
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            topic:
              type: string
              example: "favorite_song"
            details:
              type: string
              example: "Hurt by Nine Inch Nails"
    responses:
      200:
        description: Memory stored successfully
      400:
        description: Missing topic or details
      403:
        description: Unauthorized
      500:
        description: Server error
    """
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    topic = data.get("topic", "").strip().lower()
    details = data.get("details", "").strip()

    if not topic or not details:
        return jsonify({"error": "Missing topic or details"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO memory (topic, details, timestamp) VALUES (%s, %s, %s) "
            "ON CONFLICT (topic) DO UPDATE SET details = EXCLUDED.details, timestamp = EXCLUDED.timestamp;",
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
    """Retrieve memory details by topic.
    ---
    parameters:
      - name: X-API-KEY
        in: header
        type: string
        required: true
      - name: topic
        in: query
        type: string
        required: true
        example: "favorite_song"
    responses:
      200:
        description: Memory retrieved successfully
      400:
        description: No topic provided
      403:
        description: Unauthorized
      404:
        description: No memory found
      500:
        description: Server error
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
            return jsonify({"memory": result[0], "timestamp": result[1]}), 200
        else:
            return jsonify({"memory": "No memory found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/list-memories", methods=["GET"])
def list_memories():
    """Retrieve a list of all stored memories.
    ---
    parameters:
      - name: X-API-KEY
        in: header
        type: string
        required: true
    responses:
      200:
        description: List of stored memories
      403:
        description: Unauthorized
      500:
        description: Server error
    """
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT topic, details, timestamp FROM memory ORDER BY timestamp DESC;")
        results = cursor.fetchall()
        cursor.close()
        conn.close()

        memories = [{"topic": row[0], "details": row[1], "timestamp": row[2]} for row in results]
        return jsonify({"memories": memories}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/ping-db", methods=["HEAD", "GET"])
def ping_db():
    """Ping the database to keep it alive.
    ---
    responses:
      200:
        description: Database is active
      500:
        description: Database error
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)