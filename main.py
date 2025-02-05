from flask import Flask, request, jsonify
import psycopg2
import os

app = Flask(__name__)

# Database connection settings (Replace with your actual Render PostgreSQL database URL)
DATABASE_URL = os.getenv("DATABASE_URL")  # Ensure this is set in Render
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set!")

def get_db_connection():
    """ Establishes a connection to the PostgreSQL database """
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    return conn

# Initialize the database (Create the table if it doesn't exist)
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            topic TEXT PRIMARY KEY,
            details TEXT
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

# API Route to Save a Memory
@app.route("/remember", methods=["POST"])
def remember():
    """ Stores a new memory in the database """
    data = request.json
    topic = data.get("topic")
    details = data.get("details")

    if not topic or not details:
        return jsonify({"error": "Missing topic or details"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO memory (topic, details) VALUES (%s, %s) ON CONFLICT (topic) DO UPDATE SET details = EXCLUDED.details", (topic, details))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": f"Memory stored for {topic}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API Route to Recall a Memory
@app.route("/recall", methods=["GET"])
def recall():
    """ Retrieves a stored memory from the database """
    topic = request.args.get("topic")
    if not topic:
        return jsonify({"error": "Missing topic parameter"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT details FROM memory WHERE topic = %s", (topic,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            return jsonify({"memory": result[0]}), 200
        else:
            return jsonify({"memory": "No memory found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API Route to Keep Database Awake (For UptimeRobot)
@app.route("/ping-db", methods=["GET"])
def ping_db():
    """ Pings the database to keep it awake """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")  # Simple query
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "Database is awake"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Initialize the database when the app starts
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8080)
