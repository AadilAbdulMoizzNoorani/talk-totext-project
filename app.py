import os
import tempfile
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from flask_mail import Mail, Message
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# JWT configuration
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "super-secret-key")

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")

# Initialize extensions
jwt = JWTManager(app)
bcrypt = Bcrypt(app)
mail = Mail(app)

# MongoDB connection
mongo_uri = os.getenv("MONGO_URI")
if mongo_uri:
    client = MongoClient(mongo_uri)
    db = client["TextToTalk_PRO"]
    users_collection = db["users"]
    history_collection = db["history"]
else:
    # Fallback to local SQLite or other database if needed
    pass

# Auth functions
def register_user(firstname, lastname, email, password):
    try:
        # Check if user already exists
        if users_collection.find_one({"email": email}):
            return jsonify({"error": "User already exists"}), 400
        
        # Hash password
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        # Create user document
        user = {
            "firstname": firstname,
            "lastname": lastname,
            "email": email,
            "password": hashed_password,
            "created_at": datetime.datetime.utcnow()
        }
        
        # Insert user
        result = users_collection.insert_one(user)
        return jsonify({
            "message": "User created successfully",
            "user_id": str(result.inserted_id)
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def login_user(email, password):
    try:
        # Find user
        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"error": "Invalid credentials"}), 401
        
        # Check password
        if not bcrypt.check_password_hash(user["password"], password):
            return jsonify({"error": "Invalid credentials"}), 401
        
        # Generate access token (you'll need to implement JWT token creation)
        # For now, return user ID
        return jsonify({
            "message": "Login successful",
            "user_id": str(user["_id"])
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def get_profile(user_id):
    try:
        user = users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Remove password from response
        user["_id"] = str(user["_id"])
        del user["password"]
        
        return jsonify(user), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def edit_profile(user_id, data):
    try:
        # Remove fields that shouldn't be updated
        update_data = {k: v for k, v in data.items() if k != "password" and k != "_id"}
        
        # If password is being updated, hash it
        if "password" in data:
            update_data["password"] = bcrypt.generate_password_hash(data["password"]).decode('utf-8')
        
        result = users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            return jsonify({"message": "No changes made"}), 200
        
        return jsonify({"message": "Profile updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def logout_user():
    # With JWT, logout is handled on the client side by removing the token
    return jsonify({"message": "Logged out successfully"}), 200

# AI Service functions
def api(audio_path):
    # Implement your AI service logic here
    # This is a placeholder implementation
    return "This is a mock response from the AI service"

def get_history(user_id):
    try:
        history = list(history_collection.find({"user_id": user_id}).sort("created_at", -1))
        for item in history:
            item["_id"] = str(item["_id"])
        return jsonify(history), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def delete_single_history(history_id):
    try:
        result = history_collection.delete_one({"_id": ObjectId(history_id)})
        if result.deleted_count == 0:
            return jsonify({"error": "History item not found"}), 404
        return jsonify({"message": "History item deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def delete_all_history(user_id):
    try:
        result = history_collection.delete_many({"user_id": user_id})
        return jsonify({
            "message": f"Deleted {result.deleted_count} history items"
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def delete_multiple_history(history_ids):
    try:
        object_ids = [ObjectId(h_id) for h_id in history_ids]
        result = history_collection.delete_many({"_id": {"$in": object_ids}})
        return f"Deleted {result.deleted_count} history items"
    except Exception as e:
        return str(e)

# Routes
@app.route("/")
def home():
    return "Hello, API is running!"

# Auth Routes
@app.route("/auth/register", methods=["POST"])
def register():
    data = request.json
    return register_user(
        data["firstname"], 
        data["lastname"], 
        data["email"], 
        data["password"]
    )

@app.route("/auth/login", methods=["POST"])
def login():
    data = request.json
    return login_user(data["email"], data["password"])

@app.route("/auth/profile", methods=["GET"])
@jwt_required()
def profile():
    user_id = get_jwt_identity()
    return get_profile(user_id)

@app.route("/auth/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    user_id = get_jwt_identity()
    data = request.json
    return edit_profile(user_id, data)

@app.route("/logout", methods=["POST"])
@jwt_required()
def logout_route():
    return logout_user()

# Audio API Route
@app.route("/chat/", methods=["POST"])
def appi_post():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio = request.files["audio"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio_file:
        audio.save(temp_audio_file)
        temp_path = temp_audio_file.name

    try:
        result = api(temp_path)
        return jsonify({"response": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# History Routes
@app.route("/history", methods=['GET'])
def history():
    u_id = request.args.get("user_id")
    return get_history(u_id)

@app.route("/delete-history", methods=['DELETE'])
def del_history():
    h_id = request.args.get("history_id")
    return delete_single_history(h_id)

@app.route("/delete/all/history", methods=['DELETE'])
def del_all_history():
    user_id = request.args.get("user_id")
    return delete_all_history(user_id)

@app.route("/delete/select/history", methods=['POST'])
def del_select_history():
    data = request.get_json()
    history_ids = data.get("history_ids", [])

    if not history_ids:
        return jsonify({"message": "no history IDs provided"}), 400

    result = delete_multiple_history(history_ids)
    return jsonify({"message": result})

# Email Route
@app.route("/send-pdf-email", methods=["POST"])
@jwt_required()
def send_pdf_email():
    if 'file' not in request.files or not request.form.get('emailTo'):
        return jsonify({'error': 'Missing PDF file or email'}), 400

    pdf_file = request.files['file']
    email_to = request.form.get('emailTo')
    user_id = get_jwt_identity()

    pdf_bytes = pdf_file.read()

    # Send email
    msg = Message(
        subject="Your PDF Summary",
        sender=os.getenv("MAIL_USERNAME"),
        recipients=[email_to]
    )
    msg.body = "Please find attached your PDF summary."
    msg.attach(pdf_file.filename, "application/pdf", pdf_bytes)

    try:
        mail.send(msg)

        # Save history in MongoDB
        history_collection.insert_one({
            "user_id": user_id,
            "type": "email",
            "content": f"PDF sent to {email_to}",
            "filename": pdf_file.filename,
            "created_at": datetime.datetime.utcnow()
        })

        return jsonify({"message": f"Email sent to {email_to}"})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(debug=True)