from flask import Flask, request, jsonify
import psycopg2
import os

app = Flask(__name__)

# Load environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
API_KEY = os.getenv("API_KEY")

# Ensure DB connection
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# Ensure table exists
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            topic TEXT PRIMARY KEY,
            details TEXT
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
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    topic = data.get("topic", "").strip().lower()
    details = data.get("details", "").strip()

    if not topic or not details:
        return jsonify({"error": "Invalid data"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO memory (topic, details) VALUES (%s, %s) ON CONFLICT (topic) DO UPDATE SET details = EXCLUDED.details;", (topic, details))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": f"Memory stored: '{topic}' -> '{details}'"}), 200

# Route: Retrieve memory
@app.route("/recall", methods=["GET"])
def recall():
    if not check_api_key(request):
        return jsonify({"error": "Unauthorized"}), 403

    topic = request.args.get("topic", "").strip().lower()
    if not topic:
        return jsonify({"error": "No topic provided"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT details FROM memory WHERE topic = %s;", (topic,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    return jsonify({"memory": result[0] if result else "No memory found"}), 200

# Route: Keep database alive (for UptimeRobot)
@app.route("/ping-db", methods=["GET"])
def ping_db():
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