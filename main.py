from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)
MEMORY_FILE = "infobuddy_memory.json"  # Updated to match your filename

# Function to load existing memory from file
def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return {}

# Function to save memory to file
def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f)

# Load memory on startup
memory = load_memory()

@app.route('/remember', methods=['POST'])
def remember():
    data = request.json
    topic = data.get("topic")
    details = data.get("details")

    if not topic or not details:
        return jsonify({"error": "Both 'topic' and 'details' are required"}), 400

    memory[topic] = details
    save_memory(memory)  # Save to file
    return jsonify({"message": "Memory saved successfully"}), 200

@app.route('/recall', methods=['GET'])
def recall():
    topic = request.args.get("topic")
    if not topic:
        return jsonify({"error": "Topic is required"}), 400

    details = memory.get(topic, "No memory found.")
    return jsonify({"memory": details}), 200

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080)


'''import json
import os
from flask import Flask, request, jsonify

# Initialize Flask app
app = Flask(__name__)

# File to store memories
MEMORY_FILE = "infobuddy_memory.json"

def load_memory():
    """Load memories from a JSON file."""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return {}  # Return empty if file is corrupted
    return {}

def save_memory(memories):
    """Save memories to a JSON file."""
    with open(MEMORY_FILE, "w") as file:
        json.dump(memories, file, indent=4)

def store_memory(topic, details):
    """Save a memory locally (flipping key-value)."""
    topic = topic.strip().lower()
    details = details.strip().lower()
    memories = load_memory()
    memories[topic] = details
    save_memory(memories)
    return f"Stored: '{topic}' -> '{details}'"

def retrieve_memory(topic):
    """Retrieve a memory."""
    topic = topic.strip().lower()
    memories = load_memory()
    return memories.get(topic, "No memory found.")

@app.route('/remember', methods=['POST'])
def remember():
    """API Endpoint to store a memory."""
    data = request.json
    if "topic" in data and "details" in data:
        message = store_memory(data["topic"], data["details"])
        return jsonify({"message": message})
    return jsonify({"error": "Invalid request"}), 400

@app.route('/recall', methods=['GET'])
def recall():
    """API Endpoint to retrieve a memory."""
    topic = request.args.get("topic", "").strip().lower()
    if not topic:
        return jsonify({"error": "No topic provided"}), 400
    memory = retrieve_memory(topic)
    return jsonify({"memory": memory})

@app.route('/')
def home():
    return "InfoBuddy Memory API is running! Available endpoints: /recall?topic=your_topic and /remember (POST)"

if __name__ == '__main__':
        app.run(host='0.0.0.0', port=8080, debug=True)

@app.route('/')
def home():
    return "InfoBuddy Memory API is running!"'''