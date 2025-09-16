from flask import Flask
from flask_cors import CORS
from routes.faculty_routes import faculty_bp
from routes.timetable_routes import timetable_bp
from routes.auth import auth_bp   

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:5173"}}, supports_credentials=True)

@app.route("/")
def home():
    return {"message": "Backend is running "}


app.register_blueprint(auth_bp, url_prefix="/api") 
app.register_blueprint(faculty_bp, url_prefix="/api/faculty")
app.register_blueprint(timetable_bp, url_prefix="/api/timetable")

if __name__ == "__main__":
     app.run(host="0.0.0.0", port=5000, debug=False)

