from flask import Flask, request, jsonify
from flask_cors import CORS
from flasgger import Swagger
import psycopg2
import os

app = Flask(__name__)
CORS(app)

# Swagger configuration
app.config['SWAGGER'] = {
    'title': "InfoBuddy Memory API",
    'uiversion': 3
}
swagger = Swagger(app)

# Database connection setup
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set.")

conn = psycopg2.connect(DATABASE_URL, sslmode='require')

def get_db_connection():
    try:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    except Exception as e:
        print(f"Database connection error: {str(e)}")
        return None

@app.route('/ping-db', methods=['GET'])
def ping_db():
    """
    Checks database connection status.
    ---
    responses:
      200:
        description: Database connection is active.
    """
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        return jsonify({"status": "Database connection active"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/remember', methods=['POST'])
def remember():
    """
    Stores a memory with a topic and details.
    ---
    parameters:
      - name: topic
        in: formData
        type: string
        required: true
        description: The topic of the memory.
      - name: details
        in: formData
        type: string
        required: true
        description: The details of the memory.
    responses:
      200:
        description: Memory stored successfully.
      400:
        description: Missing parameters.
    """
    data = request.json
    topic = data.get("topic")
    details = data.get("details")

    if not topic or not details:
        return jsonify({"error": "Missing topic or details"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO memory (topic, details, timestamp) VALUES (%s, %s, NOW())", (topic, details))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Memory stored successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/recall', methods=['GET'])
def recall():
    """
    Retrieves a memory by topic.
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
      400:
        description: Missing topic parameter.
      404:
        description: Memory not found.
    """
    topic = request.args.get("topic")

    if not topic:
        return jsonify({"error": "Missing topic parameter"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT details, timestamp FROM memory WHERE topic = %s", (topic,))
        memory = cur.fetchone()
        cur.close()
        conn.close()

        if memory:
            return jsonify({"topic": topic, "details": memory[0], "timestamp": memory[1]}), 200
        else:
            return jsonify({"error": "Memory not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return "Welcome to the InfoBuddy Memory API! Navigate to /apidocs/ for API documentation."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
