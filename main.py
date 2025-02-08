import os
import psycopg2
from flask import Flask, request, jsonify
from flask_cors import CORS
from flasgger import Swagger
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)
Swagger(app)

# Fetch API Key and Database URL from Environment Variables
DB_URL = os.getenv("DATABASE_URL")
API_KEY = os.getenv("API_KEY")

def get_db_connection():
    """Establish a database connection."""
    return psycopg2.connect(DB_URL)

@app.route("/recall", methods=["GET"])
def recall_memory():
    """
    Recall a stored memory based on a topic.
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
        description: Missing topic parameter.
      404:
        description: No memory found.
      500:
        description: Internal server error.
    """
    user_key = request.headers.get("X-API-KEY")
    if user_key != API_KEY:
        return jsonify({"error": "Unauthorized"}), 403

    topic = request.args.get("topic")
    if not topic:
        return jsonify({"error": "Missing topic"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT details, timestamp FROM memory WHERE topic = %s", (topic,))
        result = cursor.fetchone()
        conn.close()

        if result:
            details, timestamp = result
            return jsonify({
                "memory": details,
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S %Z")
            }), 200
        else:
            return jsonify({"memory": "No memory found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/remember", methods=["POST"])
def remember_memory():
    """
    Store or update a memory with a timestamp.
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
        description: Memory saved successfully.
      403:
        description: Unauthorized access.
      400:
        description: Missing topic or details.
      500:
        description: Internal server error.
    """
    user_key = request.headers.get("X-API-KEY")
    if user_key != API_KEY:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    topic = data.get("topic")
    details = data.get("details")

    if not topic or not details:
        return jsonify({"error": "Missing topic or details"}), 400

    timestamp = datetime.utcnow()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO memory (topic, details, timestamp)
            VALUES (%s, %s, %s)
            ON CONFLICT (topic)
            DO UPDATE SET details = EXCLUDED.details, timestamp = EXCLUDED.timestamp
            """,
            (topic, details, timestamp)
        )
        conn.commit()
        conn.close()
        return jsonify({"status": "Memory saved", "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/ping-db", methods=["HEAD"])
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
        conn.close()
        return '', 200
    except Exception:
        return '', 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
