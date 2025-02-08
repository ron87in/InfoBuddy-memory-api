import os
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import psycopg2

# Load environment variables
load_dotenv()

# Securely retrieve API key
API_KEY = os.getenv("API_KEY")

if not API_KEY:
    raise ValueError("API_KEY environment variable is missing!")

# Initialize Flask
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

# Database connection settings
DATABASE_URL = os.getenv("DATABASE_URL")

# Ensure database URL is set
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is missing!")

def get_db_connection():
    """Establish a connection to the database."""
    return psycopg2.connect(DATABASE_URL)

@app.route("/")
def home():
    return jsonify({"message": "InfoBuddy+ API is running!"})

@app.route("/ping-db", methods=["HEAD", "GET"])
def ping_db():
    """Check database connection."""
    try:
        conn = get_db_connection()
        conn.close()
        return jsonify({"status": "Database connection successful"}), 200
    except Exception as e:
        logging.error(f"Database connection error: {e}")
        return jsonify({"error": "Database connection failed"}), 500

@app.route("/remember", methods=["POST"])
def remember():
    """Store a memory in the database."""
    if request.headers.get("X-API-KEY") != API_KEY:
        logging.warning("Unauthorized access attempt.")
        return jsonify({"error": "Unauthorized - Invalid API Key"}), 403

    data = request.get_json()
    if not data or "topic" not in data or "details" not in data:
        return jsonify({"error": "Invalid data format"}), 400

    topic = data["topic"]
    details = data["details"]

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO memories (topic, details, timestamp) VALUES (%s, %s, NOW())",
            (topic, details),
        )
        conn.commit()
        cur.close()
        conn.close()
        logging.info(f"Stored memory: {topic}")
        return jsonify({"message": "Memory stored successfully"}), 200
    except Exception as e:
        logging.error(f"Database insertion error: {e}")
        return jsonify({"error": "Failed to store memory"}), 500

@app.route("/recall", methods=["GET"])
def recall():
    """Retrieve a memory from the database."""
    if request.headers.get("X-API-KEY") != API_KEY:
        logging.warning("Unauthorized access attempt.")
        return jsonify({"error": "Unauthorized - Invalid API Key"}), 403

    topic = request.args.get("topic")
    if not topic:
        return jsonify({"error": "Missing topic parameter"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT details, timestamp FROM memories WHERE topic = %s", (topic,))
        memory = cur.fetchone()
        cur.close()
        conn.close()

        if memory:
            details, timestamp = memory
            return jsonify({"topic": topic, "details": details, "timestamp": timestamp}), 200
        else:
            return jsonify({"error": "Memory not found"}), 404
    except Exception as e:
        logging.error(f"Database query error: {e}")
        return jsonify({"error": "Failed to retrieve memory"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)