    import os
    import psycopg2
    import json
    from flask import Flask, request, jsonify

    app = Flask(__name__)

    # Get the PostgreSQL Database URL from environment variables (set this in Render)
    DATABASE_URL = os.getenv("DATABASE_URL")

    # Function to connect to the PostgreSQL database
    def get_db_connection():
        return psycopg2.connect(DATABASE_URL, sslmode="require")

    # Initialize the database and create the table if it doesn't exist
    def init_db():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memory (
                topic TEXT PRIMARY KEY,
                details TEXT
            )
        ''')
        conn.commit()
        cursor.close()
        conn.close()

    # Initialize the database when the API starts
    init_db()

    # Route to store a memory
    @app.route('/remember', methods=['POST'])
    def remember():
        try:
            data = request.get_json()
            topic = data.get("topic")
            details = data.get("details")

            if not topic or not details:
                return jsonify({"error": "Missing topic or details"}), 400

            conn = get_db_connection()
            cursor = conn.cursor()

            # Insert or update memory in the database
            cursor.execute('''
                INSERT INTO memory (topic, details) 
                VALUES (%s, %s) 
                ON CONFLICT (topic) 
                DO UPDATE SET details = EXCLUDED.details
            ''', (topic, details))

            conn.commit()
            cursor.close()
            conn.close()

            return jsonify({"message": f"Memory saved for topic '{topic}'"}), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Route to recall a memory
    @app.route('/recall', methods=['GET'])
    def recall():
        try:
            topic = request.args.get("topic")

            if not topic:
                return jsonify({"error": "Topic is required"}), 400

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT details FROM memory WHERE topic = %s', (topic,))
            result = cursor.fetchone()

            cursor.close()
            conn.close()

            if result:
                return jsonify({"memory": result[0]}), 200
            else:
                return jsonify({"memory": "No memory found"}), 404

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Home route for testing
    @app.route('/', methods=['GET'])
    def home():
        return jsonify({"message": "InfoBuddy Memory API is running!"}), 200

    # Run the Flask application
    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=8080)
