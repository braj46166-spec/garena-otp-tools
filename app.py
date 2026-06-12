import os
import requests
from flask import Flask, render_template, request, redirect, url_for, jsonify
from pymongo import MongoClient

# MongoDB Connection (read from environment when available)
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://braj46166_db_user:1hCgVjgXKdYZE3dk@cluster0.xfodp43.mongodb.net/?appName=Cluster0")

# Initialize MongoDB client and database
client = MongoClient(MONGO_URI)
db = client["garena_tools_db"]  # Primary Database
users_collection = db["users"]  # Users collection in garena_tools_db

# Verify MongoDB connection
try:
    client.admin.command('ismaster')
    print("✅ MongoDB Connection Successful to garena_tools_db")
except Exception as e:
    print(f"⚠️  MongoDB Connection Warning: {e}")

app = Flask(__name__)

# Simple in-memory user database
users_db = {
    "mansuk444": {"password": "1234", "credits": 300},
    "user2": {"password": "pass123", "credits": 50}
}

# Read admin credentials from environment with fallbacks
ADMIN_USER = os.environ.get("ADMIN_USER", "xniteff")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "7324")

# Ensure a permanent admin exists in MongoDB and sync into in-memory users_db
try:
    admin_doc = users_collection.find_one({"username": ADMIN_USER})
    if not admin_doc:
        admin_doc = {"username": ADMIN_USER, "password": ADMIN_PASS, "credits": 999999}
        users_collection.insert_one(admin_doc)
    # Sync admin into in-memory users_db so existing login flow works
    users_db[admin_doc["username"]] = {"password": admin_doc["password"], "credits": admin_doc.get("credits", 0)}
except Exception as e:
    # If MongoDB is unreachable, continue with in-memory users only
    app.logger.error("Failed to ensure admin in MongoDB: %s", e)

EXTERNAL_OTP_API = "https://exeotp.onrender.com/send_code"

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/regester')
def regester():
    return render_template('regester.html')

@app.route('/dashboard')
def dashboard():
    username = request.args.get('username', 'Guest')
    user = users_db.get(username)
    credits = user["credits"] if user else request.args.get('credits', '0')
    return render_template('dashboard.html', username=username, credits=credits)

@app.route('/login', methods=['POST'])
def login_post():
    username = request.form.get('username')
    password = request.form.get('password')

    # Check in-memory first, then MongoDB
    user = users_db.get(username)
    
    # Try to sync from MongoDB if user not in memory
    if not user:
        try:
            user_doc = users_collection.find_one({"username": username})
            if user_doc:
                user = {
                    "password": user_doc.get('password', ''),
                    "credits": user_doc.get('credits', 0)
                }
                users_db[username] = user  # Sync to memory
        except Exception as e:
            app.logger.error(f"MongoDB lookup failed: {e}")
    
    if user and user["password"] == password:
        return redirect(url_for('dashboard', username=username, credits=user["credits"]))

    return "Invalid Login! <a href='/'>Go Back</a>"

@app.route('/register_user', methods=['POST'])
def register_user():
    username = request.form.get('username')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')

    if not username or not password:
        return "Username and password are required. <a href='/regester'>Go Back</a>"

    if password != confirm_password:
        return "Passwords do not match. <a href='/regester'>Go Back</a>"

    # Check both in-memory and MongoDB to prevent duplicate registrations
    if username in users_db:
        return "Username already exists. <a href='/regester'>Go Back</a>"
    
    try:
        existing_user = users_collection.find_one({"username": username})
        if existing_user:
            return "Username already exists. <a href='/regester'>Go Back</a>"
    except Exception as e:
        app.logger.error(f"MongoDB lookup failed: {e}")
    
    # Save to MongoDB FIRST (source of truth - garena_tools_db.users)
    try:
        users_collection.insert_one({
            "username": username,
            "password": password,
            "credits": 0
        })
        app.logger.info(f"User {username} registered in MongoDB (garena_tools_db.users)")
    except Exception as e:
        app.logger.error(f"Failed to save user to MongoDB: {e}")
        return "Registration failed. Please try again. <a href='/regester'>Go Back</a>"
    
    # Sync to in-memory database for login flow
    users_db[username] = {"password": password, "credits": 0}

    return redirect(url_for('dashboard', username=username, credits=0))

@app.route('/send_code', methods=['GET', 'POST'])
def send_code():
    email = request.args.get('email') or request.form.get('email')
    username = request.args.get('username') or request.form.get('username')

    if request.method == 'GET':
        try:
            response = requests.get(EXTERNAL_OTP_API, params={"email": email}, timeout=15)
            response_data = response.json() if response.headers.get('content-type','').startswith('application/json') else {"message": response.text}
            if isinstance(response_data, dict) and response_data.get('status') == 'success':
                return jsonify({"status": "success"})
            if isinstance(response_data, dict) and response_data.get('success') is True:
                return jsonify({"status": "success"})
            return jsonify({"status": "error", "message": response_data.get('message', 'Failed to send OTP')}), 400
        except Exception:
            return jsonify({"status": "error", "message": "Request failed"}), 502

    user = users_db.get(username)
    if not user:
        if request.accept_mimetypes.best == 'application/json':
            return jsonify({"message": "User not found", "success": False, "status": "error"}), 404
        return "User not found. <a href='/'>Login</a>"

    if user["credits"] <= 0:
        if request.accept_mimetypes.best == 'application/json':
            return jsonify({"message": "No credits available", "success": False, "status": "error", "credits": user["credits"]}), 400
        return "No credits available. <a href='/dashboard?username={0}&credits=0'>Go Back</a>".format(username)

    try:
        response = requests.get(EXTERNAL_OTP_API, params={"email": email}, timeout=15)
        try:
            response_data = response.json()
        except Exception:
            response_data = {"message": response.text}

        external_success = None
        if isinstance(response_data, dict):
            external_success = response_data.get('success')

        if external_success is True:
            user["credits"] -= 1
        elif external_success is None and response.status_code == 200:
            user["credits"] -= 1

        if request.accept_mimetypes.best == 'application/json':
            return jsonify({
                "message": "SUCCESS" if external_success is not False else "ERROR",
                "success": external_success is not False,
                "status": "success" if external_success is not False else "error",
                "result": "SUCCESS" if external_success is not False else "ERROR",
                "email": email,
                "username": username,
                "credits": user["credits"]
            })
    except Exception:
        if request.accept_mimetypes.best == 'application/json':
            return jsonify({"message": "Request failed", "success": False, "status": "error", "result": "ERROR", "credits": user["credits"]}), 502
        pass

    return redirect(url_for('dashboard', username=username, credits=user["credits"]))

@app.route('/admin-panel')
def admin_panel():
    """
    Admin panel route - Fetches ALL users directly from MongoDB (garena_tools_db.users)
    Database: MongoDB users_collection
    Does NOT sync to users_db (keeps data sources separate)
    """
    try:
        # Fetch users directly from MongoDB (source of truth)
        all_users = {}
        for user_doc in users_collection.find():
            username = user_doc.get('username')
            if username:
                all_users[username] = {
                    'password': user_doc.get('password', ''),
                    'credits': user_doc.get('credits', 0)
                }
        
        app.logger.info(f"Admin panel loaded {len(all_users)} users from MongoDB")
        return render_template('admin.html', users=all_users)
    except Exception as e:
        app.logger.error(f"Error fetching users from MongoDB: {e}")
        return f"Database Error: {str(e)} <br> <a href='/'>Go Back</a>"

@app.route('/admin')
def admin():
    """
    Legacy admin route - Fetches ALL users directly from MongoDB (garena_tools_db.users)
    Database: MongoDB users_collection
    Does NOT sync to users_db (keeps data sources separate)
    """
    try:
        # Fetch users directly from MongoDB (source of truth)
        all_users = {}
        for user_doc in users_collection.find():
            username = user_doc.get('username')
            if username:
                all_users[username] = {
                    'password': user_doc.get('password', ''),
                    'credits': user_doc.get('credits', 0)
                }
        
        app.logger.info(f"Admin loaded {len(all_users)} users from MongoDB")
        return render_template('admin.html', users=all_users)
    except Exception as e:
        app.logger.error(f"Error fetching users from MongoDB: {e}")
        return f"Database Error: {str(e)} <br> <a href='/'>Go Back</a>"

@app.route('/add_credit', methods=['POST'])
def add_credit():
    """
    Add credits to a user in MongoDB (source of truth) and sync to in-memory database
    Primary Database: MongoDB users_collection (garena_tools_db.users)
    Secondary Database: In-memory users_db (for login flow compatibility)
    """
    target_user = request.form.get('target_user')
    try:
        amount = int(request.form.get('amount', 0))
    except ValueError:
        return f"Invalid credit amount. <a href='/admin'>Go Back</a>"

    # Check if user exists in MongoDB (source of truth)
    try:
        user_doc = users_collection.find_one({"username": target_user})
        if not user_doc:
            return f"User nahi mila: {target_user} <br> <a href='/admin'>Go Back</a>"
    except Exception as e:
        app.logger.error(f"MongoDB lookup failed: {e}")
        return f"Database error. <a href='/admin'>Go Back</a>"

    # Calculate new credits
    current_credits = user_doc.get('credits', 0)
    new_credits = current_credits + amount

    # Update MongoDB (primary source of truth)
    try:
        users_collection.update_one(
            {'username': target_user},
            {'$set': {'credits': new_credits}}
        )
        app.logger.info(f"Updated {target_user} credits in MongoDB: {current_credits} -> {new_credits}")
    except Exception as e:
        app.logger.error(f"Failed to update MongoDB: {e}")
        return f"Failed to update credits. <a href='/admin'>Go Back</a>"

    # Sync to in-memory database (for login flow compatibility)
    if target_user in users_db:
        users_db[target_user]["credits"] = new_credits
    else:
        users_db[target_user] = {"password": user_doc.get('password', ''), "credits": new_credits}

    return f"✅ Success! {target_user} ke naye credits: {new_credits} <br> <a href='/admin'>Go Back</a>"

if __name__ == '__main__':
    app.run(debug=True)
