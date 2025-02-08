import os
import psycopg2
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Retrieve the database URL
DB_URL = os.getenv("DATABASE_URL")

# Debugging Step: Check if DATABASE_URL is loaded
if DB_URL:
    print("✅ Retrieved DATABASE_URL successfully.")
else:
    print("❌ DATABASE_URL is None! Check your environment variables.")

# Flask App Initialization
app = Flask(__name__)

# Function to establish database connection
def get_db_connection():
    try:
        conn = psycopg2.connect(DB_URL)
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

# API Endpoint to Check Database Connection
@app.route('/ping-db', methods=['GET'])
def ping_db():
    conn = get_db_connection()
    if conn:
        conn.close()
        return jsonify({"message": "✅ Database connection successful"}), 200
    else:
        return jsonify({"error": "❌ Failed to connect to database"}), 500

# API Endpoint to Remember a Memory
@app.route('/remember', methods=['POST'])
def remember():
    data = request.json
    topic = data.get("topic")
    details = data.get("details")

    if not topic or not details:
        return jsonify({"error": "Missing topic or details"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "❌ Failed to connect to database"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO memories (topic, details) VALUES (%s, %s)", (topic, details))
            conn.commit()
        return jsonify({"message": "✅ Memory saved successfully"}), 201
    except Exception as e:
        print(f"❌ Error saving memory: {e}")
        return jsonify({"error": "Failed to save memory"}), 500
    finally:
        conn.close()

# API Endpoint to Recall a Memory
@app.route('/recall', methods=['GET'])
def recall():
    topic = request.args.get("topic")
    if not topic:
        return jsonify({"error": "Missing topic"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "❌ Failed to connect to database"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT details FROM memories WHERE topic = %s", (topic,))
            result = cur.fetchone()
            if result:
                return jsonify({"topic": topic, "details": result[0]}), 200
            else:
                return jsonify({"error": "Memory not found"}), 404
    except Exception as e:
        print(f"❌ Error retrieving memory: {e}")
        return jsonify({"error": "Failed to retrieve memory"}), 500
    finally:
        conn.close()

# Run Flask App
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)