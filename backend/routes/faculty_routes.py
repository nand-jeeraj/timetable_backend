from flask import Blueprint, request, jsonify
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

faculty_bp = Blueprint("faculty", __name__, url_prefix="/api/faculty")
faculty_collection = db["faculties"]

def serialize_faculty(faculty):
    faculty["_id"] = str(faculty["_id"])
    return faculty


@faculty_bp.route("/", methods=["GET"])
def get_faculties():
    colid = request.args.get("colid")
    if not colid:
        return jsonify([]) 
    query = {"colid": str(colid)}  
    print("Fetching faculties with query:", query)
    faculties = list(faculty_collection.find(query))
    return jsonify([serialize_faculty(f) for f in faculties])

@faculty_bp.route("/", methods=["POST"])
def add_faculty():
    data = request.json
    name = data.get("name")
    department = data.get("department")
    semester = data.get("semester")
    available_slots = data.get("available_slots", [])
    week_start = data.get("week_start")
    minutes_per_week = data.get("minutes_per_week")
    colid = data.get("colid")

    if not all([name, department, semester, available_slots, week_start, minutes_per_week, colid]):
        return jsonify({"error": "All fields are required"}), 400

    faculty_data = {
        "name": name.strip(),
        "department": department.strip().upper(),
        "semester": int(semester),
        "available_slots": available_slots,
        "week_start": week_start,
        "minutes_per_week": int(minutes_per_week),
        "colid": str(colid),  
    }

    result = faculty_collection.insert_one(faculty_data)
    return jsonify({"message": "Faculty added successfully", "id": str(result.inserted_id)}), 201


@faculty_bp.route("/<string:faculty_id>", methods=["DELETE"])
def delete_faculty(faculty_id):
    colid = request.args.get("colid")
    if not colid:
        return jsonify({"error": "colid is required"}), 400

    query = {"_id": ObjectId(faculty_id), "colid": str(colid)}

    try:
        result = faculty_collection.delete_one(query)
    except:
        return jsonify({"error": "Invalid faculty ID"}), 400

    if result.deleted_count == 0:
        return jsonify({"error": "Faculty not found"}), 404

    return jsonify({"message": "Faculty deleted successfully"}), 200
