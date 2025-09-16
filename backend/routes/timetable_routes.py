from flask import Blueprint, request, jsonify, send_file
from pymongo import MongoClient
from collections import defaultdict
from openpyxl import Workbook
from bson import ObjectId
import io
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

timetable_bp = Blueprint("timetable", __name__, url_prefix="/api/timetable")

DAYS_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

def serialize_doc(doc):
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    return doc

def format_time_ampm(mins):
    h = mins // 60
    m = mins % 60
    am = "AM" if h < 12 else "PM"
    display_h = h % 12
    if display_h == 0:
        display_h = 12
    return f"{display_h}:{m:02d} {am}"

def subtract_used_intervals(avail_intervals, used_intervals):
    if not avail_intervals:
        return []
    avail = sorted(avail_intervals, key=lambda x: x[0])
    used = sorted(used_intervals, key=lambda x: x[0]) if used_intervals else []

    free = []
    for a_start, a_end in avail:
        cursor = a_start
        for u_start, u_end in used:
            if u_end <= cursor:
                continue
            if u_start >= a_end:
                break
            if u_start > cursor:
                free.append((cursor, min(u_start, a_end)))
            cursor = max(cursor, u_end)
            if cursor >= a_end:
                break
        if cursor < a_end:
            free.append((cursor, a_end))
    return free

def merge_intervals(intervals):
    if not intervals:
        return []
    ints = sorted(intervals, key=lambda x: x[0])
    merged = []
    cur_s, cur_e = ints[0]
    for s, e in ints[1:]:
        if s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            merged.append((cur_s, cur_e))
            cur_s, cur_e = s, e
    merged.append((cur_s, cur_e))
    return merged


@timetable_bp.route("/generate", methods=["POST"])
def generate_timetable():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    department = data.get("department")
    semester = data.get("semester")
    week_start = data.get("week_start")
    colid = request.args.get("colid")  # <-- added colid filter
    if not department or not semester or not week_start or not colid:
        return jsonify({"error": "department, semester, week_start, and colid are required"}), 400

    # Fetch faculties only for this colid
    faculties_cursor = list(
        db.faculties.find({"department": department, "semester": int(semester), "week_start": week_start, "colid": colid})
    )
    if not faculties_cursor:
        faculties_cursor = list(
            db.faculties.find({"department": department, "semester": int(semester), "colid": colid})
        )
    if not faculties_cursor:
        return jsonify({"error": "No faculties found for this department/semester/colid"}), 404

    faculty_availability = {}
    faculty_names = {}
    for f in faculties_cursor:
        fid = str(f["_id"])
        faculty_names[fid] = f.get("name", "Unknown")
        slots = []
        for slot in f.get("available_slots", []):
            if isinstance(slot, dict):
                day = slot.get("day")
                if day is None:
                    continue
                try:
                    s = int(slot.get("startMinutes") or slot.get("start"))
                    e = int(slot.get("endMinutes") or slot.get("end"))
                except Exception:
                    continue
                if e > s:
                    slots.append((day, s, e))
        faculty_availability[fid] = slots

    used_by_day = defaultdict(list)
    assignments = []

    for f in faculties_cursor:
        fid = str(f["_id"])
        faculty_name = f.get("name", "Unknown")
        minutes_left = int(f.get("minutes_per_week", 0))

        for day in DAYS_ORDER:
            if minutes_left <= 0:
                break
            day_avail = [(s, e) for (d, s, e) in faculty_availability.get(fid, []) if d == day]
            if not day_avail:
                continue

            used = used_by_day.get(day, [])
            free_intervals = subtract_used_intervals(day_avail, used)

            for fs, fe in free_intervals:
                if minutes_left <= 0:
                    break
                available_minutes = fe - fs
                take = min(available_minutes, minutes_left)
                alloc_s, alloc_e = fs, fs + take
                assignments.append({
                    "day": day,
                    "start_min": alloc_s,
                    "end_min": alloc_e,
                    "faculty_id": fid,
                    "faculty_name": faculty_name,
                })
                used_by_day[day].append((alloc_s, alloc_e))
                minutes_left -= take

    grouped = defaultdict(list)
    for a in assignments:
        key = (a["day"], a["faculty_name"])
        grouped[key].append((a["start_min"], a["end_min"]))

    schedule = []
    for (day, faculty_name), intervals in grouped.items():
        merged = merge_intervals(intervals)
        for s, e in merged:
            schedule.append({
                "day": day,
                "start_min": s,
                "end_min": e,
                "start_time": format_time_ampm(s),
                "end_time": format_time_ampm(e),
                "faculty_name": faculty_name,
            })

    schedule_sorted = sorted(
        schedule,
        key=lambda x: (DAYS_ORDER.index(x["day"]) if x["day"] in DAYS_ORDER else 999, x["start_min"])
    )

    timetable_doc = {
        "department": department,
        "semester": int(semester),
        "week_start": week_start,
        "colid": colid, 
        "schedule": schedule_sorted,
    }

    db.timetables.update_one(
        {"department": department, "semester": int(semester), "week_start": week_start, "colid": colid},
        {"$set": timetable_doc},
        upsert=True,
    )

    saved = db.timetables.find_one(
        {"department": department, "semester": int(semester), "week_start": week_start, "colid": colid}
    )
    timetable_doc["_id"] = str(saved["_id"])

    return jsonify({"message": "Timetable generated successfully", **timetable_doc}), 200



@timetable_bp.route("", methods=["GET"])
def get_timetable_by_filters():
    department = request.args.get("department")
    semester = request.args.get("semester")
    week_start = request.args.get("week_start") or request.args.get("weekStart")
    colid = request.args.get("colid")
    if not department or not semester or not week_start or not colid:
        return jsonify({"error": "department, semester, week_start, and colid are required"}), 400

    doc = db.timetables.find_one({"department": department, "semester": int(semester), "week_start": week_start, "colid": colid})
    if not doc:
        return jsonify({"error": "No timetable found"}), 404
    return jsonify(serialize_doc(doc)), 200



@timetable_bp.route("/download", methods=["GET"])
def download_timetable_excel():
    department = request.args.get("department")
    semester = request.args.get("semester")
    week_start = request.args.get("week_start") or request.args.get("weekStart")
    colid = request.args.get("colid")
    if not department or not semester or not week_start or not colid:
        return jsonify({"error": "department, semester, week_start, and colid are required"}), 400

    doc = db.timetables.find_one({"department": department, "semester": int(semester), "week_start": week_start, "colid": colid})
    if not doc:
        return jsonify({"error": "No timetable found"}), 404

    wb = Workbook()
    ws = wb.active
    ws.title = f"Sem {semester} Timetable"

    ws.append(["Department", department])
    ws.append(["Semester", semester])
    ws.append(["Week Start", week_start])
    ws.append([])
    ws.append(["Day", "Start Time", "End Time", "Faculty"])

    for s in doc.get("schedule", []):
        ws.append([s["day"], s["start_time"], s["end_time"], s["faculty_name"]])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"timetable_{department}_sem{semester}_{week_start}.xlsx"
    return send_file(output, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")



@timetable_bp.route("/options", methods=["GET"])
def get_options():
    colid = request.args.get("colid")
    if not colid:
        return jsonify({"error": "colid required"}), 400

    faculties = list(db.faculties.find({"colid": colid}))
    departments = sorted(list(set(f.get("department") for f in faculties)))
    semesters = sorted(list(set(f.get("semester") for f in faculties)))

    return jsonify({"departments": departments, "semesters": semesters})
