from flask import Flask, request, jsonify
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Database connection setup
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

@app.route("/remember", methods=["POST"])
def remember():
    data = request.json
    topic = data.get("topic")
    details = data.get("details")

    if not topic or not details:
        return jsonify({"error": "Missing topic or details"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to database"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO memory (topic, details, timestamp) VALUES (%s, %s, NOW())",
                (topic, details),
            )
        conn.commit()
        return jsonify({"message": "Memory saved successfully"}), 201
    except Exception as e:
        print(f"Database insert error: {e}")
        return jsonify({"error": "Failed to save memory"}), 500
    finally:
        conn.close()

@app.route("/recall", methods=["GET"])
def recall():
    topic = request.args.get("topic")

    if not topic:
        return jsonify({"error": "Missing topic parameter"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to database"}), 500

    try:
        with conn.cursor() as cur:
            print(f"Querying for topic: {topic}")  # Debug log
            cur.execute("SELECT details, timestamp FROM memory WHERE topic = %s", (topic,))
            result = cur.fetchone()

        if result:
            details, timestamp = result
            return jsonify({"topic": topic, "details": details, "timestamp": timestamp})
        else:
            return jsonify({"error": "Memory not found"}), 404
    except Exception as e:
        print(f"Database query error: {e}")
        return jsonify({"error": "Failed to retrieve memory"}), 500
    finally:
        conn.close()

# Debug route to list all stored memories
@app.route("/debug-db", methods=["GET"])
def debug_db():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to database"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT topic, details, timestamp FROM memory LIMIT 10;")
            results = cur.fetchall()

        return jsonify({"memories": [{"topic": row[0], "details": row[1], "timestamp": row[2]} for row in results]})
    except Exception as e:
        print(f"Database debug error: {e}")
        return jsonify({"error": "Failed to retrieve database contents"}), 500
    finally:
        conn.close()

@app.route("/ping-db", methods=["GET"])
def ping_db():
    """Check database connectivity"""
    conn = get_db_connection()
    if conn:
        conn.close()
        return jsonify({"message": "Database is reachable"}), 200
    else:
        return jsonify({"error": "Database connection failed"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)