from flask import Flask, request, jsonify
import psycopg2
import os

app = Flask(__name__)

# Database Connection Function
def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )

# Initialize Database
def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    topic TEXT PRIMARY KEY,
                    details TEXT
                );
            """)  # ✅ Fixed Syntax
            conn.commit()

# Route to Save a Memory
@app.route('/remember', methods=['POST'])
def remember():
    data = request.json
    topic = data.get("topic")
    details = data.get("details")

    if not topic or not details:
        return jsonify({"error": "Missing topic or details"}), 400

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO memory (topic, details)
                    VALUES (%s, %s)
                    ON CONFLICT (topic) DO UPDATE SET details = EXCLUDED.details;
                """, (topic, details))
                conn.commit()
        return jsonify({"message": "Memory saved successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to Recall a Memory
@app.route('/recall', methods=['GET'])
def recall():
    topic = request.args.get("topic")

    if not topic:
        return jsonify({"error": "Missing topic parameter"}), 400

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT details FROM memory WHERE topic = %s;", (topic,))
                result = cursor.fetchone()

        if result:
            return jsonify({"memory": result[0]})
        else:
            return jsonify({"memory": "No memory found."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Main Execution
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8080)