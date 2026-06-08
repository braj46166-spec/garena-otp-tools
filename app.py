import os
import requests
from flask import Flask, render_template, request, redirect, url_for, jsonify
from pymongo import MongoClient
from urllib.parse import unquote

# MongoDB Connection (read from environment when available)
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://braj46166_db_user:1hCgVjgXKdYZE3dk@cluster0.xfodp43.mongodb.net/?appName=Cluster0")

client = MongoClient(MONGO_URI)
db = client["garena_tools_db"]
users_collection = db["users"]

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

EXTERNAL_OTP_API = "https://vinnyyy-otp-sender.vercel.app/api/send-otp"

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

    user = users_db.get(username)
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

    if username in users_db:
        return "Username already exists. <a href='/regester'>Go Back</a>"

    users_db[username] = {"password": password, "credits": 0}
    return redirect(url_for('dashboard', username=username, credits=0))

@app.route('/send_code', methods=['POST'])
def send_code():
    username = request.form.get('username')
    credits = int(request.form.get('credits', 0))
    email = request.form.get('email')

    user = users_db.get(username)
    if not user:
        return "User not found. <a href='/'>Login</a>"

    if user["credits"] <= 0:
        return "No credits available. <a href='/dashboard?username={0}&credits=0'>Go Back</a>".format(username)

    # Send external request first and decrement only when the external API reports success
    try:
        response = requests.get(f"{EXTERNAL_OTP_API}/{email}", timeout=15)
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
    except Exception:
        # External API failed or timed out; do not decrement credits
        pass

    return redirect(url_for('dashboard', username=username, credits=user["credits"]))

@app.route('/api/send-otp/')
@app.route('/api/send-otp/<path:email>')
def api_send_otp(email=None):
    username = request.args.get('username')
    email = email or request.args.get('email')
    
    # Decode URL-encoded email
    if email:
        email = unquote(email)
    
    app.logger.info(f"API called: email={email}, username={username}")

    if not email:
        return jsonify({
            "message": "Garena OTP Handler API is running smoothly",
            "success": False,
            "status": "online",
            "usage_example": "Append '/api/send-otp/your-email@gmail.com?username=youruser' to your URL"
        })

    if not username:
        return jsonify({
            "message": "Username is required for sending OTP",
            "success": False,
            "status": "error",
            "usage_example": "Append '?username=youruser' to the URL"
        })

    user = users_db.get(username)
    if not user:
        return jsonify({
            "message": "User not found",
            "success": False,
            "status": "error"
        })

    if user["credits"] <= 0:
        return jsonify({
            "message": "No credits available",
            "success": False,
            "status": "error",
            "credits": user["credits"]
        })

    try:
        external_response = requests.get(f"{EXTERNAL_OTP_API}/{email}", timeout=15)
        # try to parse JSON, but handle non-JSON gracefully
        try:
            external_data = external_response.json()
        except Exception:
            external_data = {"message": external_response.text}

        app.logger.info(f"External API response: status={external_response.status_code}, data={external_data}")
    except Exception:
        # External API failed or timed out; do not decrement credits
        return jsonify({
            "message": "Request failed",
            "success": False,
            "status": "error",
            "result": "ERROR",
            "credits": user["credits"]
        })

    external_message = (external_data.get('message') if isinstance(external_data, dict) else None) or \
                       (external_data.get('error') if isinstance(external_data, dict) else None) or \
                       str(external_data)

    external_status = ''
    external_success_flag = None
    if isinstance(external_data, dict):
        external_status = str(external_data.get('status', '')).strip().lower()
        external_success_flag = external_data.get('success')
    
    app.logger.info(f"Parsed: external_success_flag={external_success_flag}, external_status={external_status}")

    is_external_success = False
    if external_success_flag is True:
        is_external_success = True
        app.logger.info("Success detected: external_success_flag is True")
    elif external_success_flag is False:
        is_external_success = False
        app.logger.info("Failure detected: external_success_flag is False")
    elif external_response.status_code == 200 and external_status not in ('error', 'failed', 'failure', 'false'):
        is_external_success = True
        app.logger.info(f"Success detected: status_code={external_response.status_code}, status={external_status}")
    else:
        app.logger.info(f"Failure: status_code={external_response.status_code}, status={external_status}, success_flag={external_success_flag}")

    if is_external_success:
        user["credits"] -= 1
        return jsonify({
            "message": "SUCCESS",
            "success": True,
            "status": "success",
            "result": "SUCCESS",
            "email": email,
            "username": username,
            "credits": user["credits"]
        })

    return jsonify({
        "message": "ERROR",
        "success": False,
        "status": "error",
        "result": "ERROR",
        "credits": user["credits"]
    })

@app.route('/admin')
def admin():
    return render_template('admin.html', users=users_db)

@app.route('/add_credit', methods=['POST'])
def add_credit():
    target_user = request.form.get('target_user')
    amount = int(request.form.get('amount', 0))

    if target_user in users_db:
        users_db[target_user]["credits"] += amount
        return f"Success! {target_user} ke naye credits: {users_db[target_user]['credits']} <br> <a href='/admin'>Go Back</a>"
    return "User nahi mila! <a href='/admin'>Go Back</a>"

if __name__ == '__main__':
    app.run(debug=True)
