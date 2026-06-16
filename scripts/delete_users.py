from pymongo import MongoClient
import os

MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://braj46166_db_user:1hCgVjgXKdYZE3dk@cluster0.xfodp43.mongodb.net/?appName=Cluster0")
client = MongoClient(MONGO_URI)
db = client["garena_tools_db"]
users_collection = db["users"]

users_to_delete = ["mansuk444", "user2"]
for u in users_to_delete:
    try:
        res = users_collection.delete_many({"username": u})
        print(f"Deleted {res.deleted_count} documents for user '{u}'")
    except Exception as e:
        print(f"Error deleting user {u}: {e}")
