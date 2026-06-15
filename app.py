import os
import requests
from flask import Flask, render_template, request, redirect, url_for, jsonify
from pymongo import MongoClient

# MongoDB Connection
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://braj46166_db_user:1hCgVjgXKdYZE3dk@cluster0.xfodp43.mongodb.net/?appName=Cluster0")
client = MongoClient(MONGO_URI)
db = client["garena_tools_db"]
users_collection = db["users"]

app = Flask(__name__)

# Empty in-memory database - sirf Admin ke liye use hoga
users_db = {}

ADMIN_USER = os.environ.get("ADMIN_USER", "xniteff")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "7324")

# Admin setup
try:
    admin_doc = users_collection.find_one({"username": ADMIN_USER})
    if not admin_doc:
        admin_doc = {"username": ADMIN_USER, "password": ADMIN_PASS, "credits": 999999}
        users_collection.insert_one(admin_doc)
    # Admin ko memory mein sync rakhein
    users_db[admin_doc["username"]] = {"password": admin_doc["password"], "credits": admin_doc.get("credits", 0)}
except:
    pass

EXTERNAL_OTP_API = "https://exeotp.onrender.com/send_code"

@app.route('/')
def login(): return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    username = request.args.get('username', 'Guest')
    user = users_db.get(username)
    credits = user["credits"] if user else request.args.get('credits', '0')
    return render_template('dashboard.html', username=username, credits=credits)

@app.route('/send_code', methods=['POST'])
def send_code():
    email = request.form.get('email')
    username = request.form.get('username')

    user_doc = users_collection.find_one({"username": username})
    if not user_doc:
        return jsonify({"status": "error", "message": "User not found", "email": email, "remaining_credits": 0}), 404

    current_credits = user_doc.get("credits", 0)
    if current_credits <= 0:
        return jsonify({"status": "error", "message": "No credits available", "email": email, "remaining_credits": current_credits}), 400

    try:
        response = requests.get(EXTERNAL_OTP_API, params={"email": email}, timeout=15)
        response_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {"message": response.text}
        
        success = response.status_code == 200
        
        if success:
            users_collection.update_one({"username": username}, {"$inc": {"credits": -1}})
            current_credits -= 1
            if username in users_db: users_db[username]["credits"] = current_credits
            
            return jsonify({
                "status": "success",
                "message": "Code sent successfully!",
                "email": email,
                "remaining_credits": current_credits
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to send OTP",
                "email": email,
                "remaining_credits": current_credits
            }), 400
    except Exception as e:
        return jsonify({"status": "error", "message": "Request failed", "email": email, "remaining_credits": current_credits}), 502

if __name__ == '__main__':
    app.run(debug=True)