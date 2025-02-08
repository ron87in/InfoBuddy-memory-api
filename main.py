from flask import Flask, request, jsonify
import psycopg2
import os
import datetime
import pytz
import json
from dateutil import parser
from flasgger import Swagger

app = Flask(__name__)
swagger = Swagger(app)

# Retrieve API Key from environment variable
API_KEY = os.getenv("API_KEY")

# Database connection function
def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# Middleware to check API Key
def verify_api_key():
    key = request.headers.get("X-API-KEY") or request.headers.get("Authorization")

    # If Authorization header is used, extract Bearer token
    if key and key.startswith("Bearer "):
        key = key.split(" ")[1]

    if key != API_KEY:
        return jsonify({"error": "Unauthorized access"}), 403

# Endpoint to save memory with timestamp
@app.route("/remember", methods=["POST"])
def remember():
    """
    Save a memory
    ---
    tags:
      - Memory
    parameters:
      - name: X-API-KEY
        in: header
        type: string
        required: true
        description: API Key for authentication
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - topic
            - details
          properties:
            topic:
              type: string
              example: "test_memory"
            details:
              type: string
              example: "This is a test entry"
    responses:
      200:
        description: Memory saved
    """
    error = verify_api_key()
    if error:
        return error

    data = request.json
    topic = data.get("topic")
    details = data.get("details")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO memory (topic, details, timestamp) VALUES (%s, %s, NOW()) "
            "ON CONFLICT (topic) DO UPDATE SET details = EXCLUDED.details, timestamp = NOW();",
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
    """
    Retrieve a memory
    ---
    tags:
      - Memory
    parameters:
      - name: X-API-KEY
        in: header
        type: string
        required: true
        description: API Key for authentication
      - name: topic
        in: query
        type: string
        required: true
        description: Topic of the memory to recall
    responses:
      200:
        description: Memory retrieved
        schema:
          type: object
          properties:
            memory:
              type: string
              example: "This is a test entry"
            timestamp:
              type: string
              example: "2025-02-06T12:34:56Z"
      403:
        description: Unauthorized access (API key missing or invalid)
    """
    error = verify_api_key()
    if error:
        return error

    topic = request.args.get("topic")
    if not topic:
        return jsonify({"error": "Missing 'topic' query parameter"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT details, timestamp FROM memory WHERE topic = %s", (topic,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            details, timestamp = result
            return jsonify({"memory": details, "timestamp": timestamp.isoformat()}), 200
        else:
            return jsonify({"memory": "No memory found"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Swagger UI Route
@app.route("/apidocs/")
def apidocs():
    """
    API Documentation
    ---
    responses:
      200:
        description: Swagger UI for API documentation
    """
    return jsonify({"message": "Swagger UI available at /apidocs/"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
