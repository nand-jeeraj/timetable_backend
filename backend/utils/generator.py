from pymongo import MongoClient
import random
from bson import ObjectId

client = MongoClient("mongodb+srv://nand27:Nand27113@cluster.gbexk9t.mongodb.net/attendance_db?retryWrites=true&w=majority&appName=Cluster")
db = client["timetable_db"]

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
SLOTS = ["9-10", "10-11", "11-12", "1-2", "2-3"]  # You can adjust

def generate_timetable():
    faculties = list(db.faculties.find())
    subjects = list(db.subjects.find())

    timetable = []
    used_slots = set()  # prevent duplicate slot allocation

    for subj in subjects:
        faculty = db.faculties.find_one({"_id": subj["faculty_id"]})
        if not faculty:
            print(f"⚠️ Faculty not found for subject {subj['_id']}")
            continue

        # assign subject to random available slot(s)
        hours = subj.get("hours_per_week", 2)
        allocated = 0

        while allocated < hours:
            day = random.choice(DAYS)
            slot = random.choice(SLOTS)
            slot_key = f"{faculty['_id']}-{day}-{slot}"

            if slot_key not in used_slots and f"{day}-{slot}" in faculty.get("available_slots", []):
                timetable_entry = {
                    "faculty_id": faculty["faculty_id"],
                    "subject_id": subj["_id"],
                    "day": day,
                    "slot": slot
                }
                db.timetable.insert_one(timetable_entry)
                timetable.append(timetable_entry)
                used_slots.add(slot_key)
                allocated += 1

    return timetable
