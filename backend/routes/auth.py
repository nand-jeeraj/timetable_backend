from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, current_user
from werkzeug.security import check_password_hash
from .user import DummyUser
from pymongo import MongoClient
import os

auth_bp = Blueprint("auth", __name__)

client = MongoClient(os.getenv("MONGO_URI"))
db = client["test"] 
users_collection = db["users"]   

@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password required'}), 400

        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        # If passwords are hashed
        from werkzeug.security import check_password_hash
        if not check_password_hash(user["password"], password):
            return jsonify({'success': False, 'message': 'Invalid password'}), 401

        return jsonify({
            'success': True,
            'name': user.get('name'),
            'user_id': str(user["_id"]),
            'colid': user.get('colid'),
            'token': "dummy-session-token"
        })
    except Exception as e:
        print("Login error:", e) 
        return jsonify({'success': False, 'message': 'Server error'}), 500

@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return jsonify({"success": True})

@auth_bp.route("/check-auth")
def check_auth():
    if current_user.is_authenticated:
        return jsonify({"status": "ok"})
    return jsonify({"status": "unauthorized"}), 401
