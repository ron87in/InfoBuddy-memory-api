from flask import Flask, request, jsonify
from flasgger import Swagger
from flask_cors import CORS
import os
import psycopg2

app = Flask(__name__)
CORS(app)  # Enables CORS (in case Swagger isn't loading due to CORS)
swagger = Swagger(app)  # Initializes Swagger UI

# ✅ Environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
API_KEY = os.getenv("API_KEY")

# ✅ Database Connection
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

# ✅ Security - API Key Check
def verify_api_key():
    key = request.headers.get("X-API-KEY")
    if key != API_KEY:
        return jsonify({"error": "Invalid API key"}), 403

# ✅ Ping Database Route
@app.route("/ping-db", methods=["HEAD"])
def ping_db():
    """Check database connection
    ---
    responses:
      200:
        description: Database is online
    """
    try:
        conn = get_db_connection()
        conn.close()
        return "", 200
    except:
        return "", 500

# ✅ Store Memory Route
@app.route("/remember", methods=["POST"])
def remember():
    """Store a memory
    ---
    parameters:
      - name: topic
        in: formData
        type: string
        required: true
      - name: details
        in: formData
        type: string
        required: true
    responses:
      200:
        description: Memory stored successfully
    """
    auth_check = verify_api_key()
    if auth_check:
        return auth_check

    data = request.json
    topic = data.get("topic")
    details = data.get("details")

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

# ✅ Retrieve Memory Route
@app.route("/recall", methods=["GET"])
def recall():
    """Retrieve a memory
    ---
    parameters:
      - name: topic
        in: query
        type: string
        required: true
    responses:
      200:
        description: Memory retrieved
    """
    auth_check = verify_api_key()
    if auth_check:
        return auth_check

    topic = request.args.get("topic")

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT details FROM memory WHERE topic = %s ORDER BY timestamp DESC LIMIT 1", (topic,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row:
            return jsonify({"memory": row[0]}), 200
        else:
            return jsonify({"error": "Memory not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Run the App
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)