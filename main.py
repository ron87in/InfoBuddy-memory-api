import os
import psycopg2
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Retrieve API key
API_KEY = os.getenv("API_KEY")
DB_URL = os.getenv("DATABASE_URL")

if not API_KEY:
    print("ERROR: API_KEY is not set!")

if not DB_URL:
    print("ERROR: DATABASE_URL is not set!")

def get_db_connection():
    try:
        conn = psycopg2.connect(DB_URL)
        print("Database connection successful.")
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

@app.route("/recall", methods=["GET"])
def recall():
    try:
        user_api_key = request.headers.get("X-API-KEY")

        if not user_api_key:
            print("Unauthorized access: No API key provided.")
            return jsonify({"error": "Unauthorized - No API Key"}), 403

        if user_api_key != API_KEY:
            print("Unauthorized access attempt.")
            return jsonify({"error": "Unauthorized - Invalid API Key"}), 403

        topic = request.args.get("topic")
        if not topic:
            print("Error: No topic provided in request.")
            return jsonify({"error": "Topic parameter is required"}), 400

        conn = get_db_connection()
        if not conn:
            print("Error: Database connection failed.")
            return jsonify({"error": "Database connection failed"}), 500

        cur = conn.cursor()
        cur.execute("SELECT details FROM memories WHERE topic = %s", (topic,))
        result = cur.fetchone()
        cur.close()
        conn.close()

        if not result:
            print(f"Memory not found for topic: {topic}")
            return jsonify({"error": "Memory not found"}), 404

        print(f"Successfully retrieved memory for topic: {topic}")
        return jsonify({"topic": topic, "details": result[0]}), 200

    except Exception as e:
        print(f"Error in /recall: {e}")
        return jsonify({"error": "Failed to retrieve memory"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)