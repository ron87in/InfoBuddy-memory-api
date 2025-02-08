import os
import psycopg2
from flask import Flask, request, jsonify
from flask_cors import CORS
from flasgger import Swagger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)
Swagger(app)

# Database connection setup
DATABASE_URL = os.getenv("DATABASE_URL")
API_KEY = os.getenv("API_KEY")

if not DATABASE_URL or not API_KEY:
    raise ValueError("Missing required environment variables: DATABASE_URL or API_KEY")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

@app.route("/ping-db", methods=["HEAD"])
def ping_db():
    """Check database connectivity
    ---
    responses:
      200:
        description: Database is reachable
      500:
        description: Database connection failed
    """
    try:
        conn = get_db_connection()
        conn.close()
        return "", 200
    except Exception as e:
        return str(e), 500

@app.route("/remember", methods=["POST"])
def remember():
    """Store a memory in the database
    ---
    parameters:
      - name: X-API-KEY
        in: header
        required: true
        type: string
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            topic:
              type: string
            details:
              type: string
    responses:
      200:
        description: Memory stored successfully
      400:
        description: Missing parameters
      401:
        description: Unauthorized
      500:
        description: Internal server error
    """
    if request.headers.get("X-API-KEY") != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    topic = data.get("topic")
    details = data.get("details")

    if not topic or not details:
        return jsonify({"error": "Missing 'topic' or 'details'"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO memories (topic, details) VALUES (%s, %s)", (topic, details))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Memory stored successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/recall", methods=["GET"])
def recall():
    """Retrieve a memory from the database by topic
    ---
    parameters:
      - name: X-API-KEY
        in: header
        required: true
        type: string
      - name: topic
        in: query
        required: true
        type: string
    responses:
      200:
        description: Retrieved memory successfully
      400:
        description: Missing topic parameter
      401:
        description: Unauthorized
      404:
        description: No memory found
      500:
        description: Internal server error
    """
    if request.headers.get("X-API-KEY") != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    topic = request.args.get("topic")
    if not topic:
        return jsonify({"error": "Missing 'topic' parameter"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT details FROM memories WHERE topic = %s ORDER BY created_at DESC LIMIT 1", (topic,))
        memory = cur.fetchone()
        cur.close()
        conn.close()

        if memory:
            return jsonify({"topic": topic, "details": memory[0]}), 200
        else:
            return jsonify({"error": "No memory found for this topic"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
