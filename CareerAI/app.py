import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from pypdf import PdfReader
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path("/tmp/careerai-data") if os.getenv("VERCEL") else BASE_DIR / "data"
USERS_FILE = DATA_DIR / "users.json"
ANALYSIS_FILE = DATA_DIR / "analysis.json"

if not os.getenv("VERCEL"):
    load_dotenv(dotenv_path=BASE_DIR / ".env")

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024

CAREER_PROMPT = """Act as an expert AI Career Mentor.

Student Information:

Name:
{name}

Education:
{education}

Skills:
{skills}

Experience Level:
{experience_level}

Career Goal:
{career_goal}

Target Role:
{target_role}

Available Study Hours:
{study_hours}

Analyze the student profile.

Provide:

1. Career Profile Summary
2. 5 Suitable Job Roles
3. Current Strengths
4. Missing Skills for Target Role
5. Personalized Learning Roadmap
6. 3 Recommended Projects
7. Interview Preparation Topics
8. Career Improvement Tips

Rules:

Give personalized suggestions.

Do not invent skills.

Keep the explanation simple.

Give practical suggestions for students and freshers.
"""

RESUME_PROMPT = """Act as an expert Resume Reviewer and AI Career Coach.

Analyze the following resume.

RESUME:
{resume_text}

Target Role:
{target_role}

Experience Level:
{experience_level}

Provide:

1. Resume Profile Summary
2. Skills Identified
3. Resume Strengths
4. Resume Weak Areas
5. 5 Suitable Job Roles
6. Target Role Match Analysis
7. Missing Skills
8. Resume Improvements
9. ATS Improvement Tips
10. Learning Recommendations
11. 3 Recommended Projects
12. Job Platforms for Freshers
13. Next Career Steps

Rules:

Do not invent information.

Only analyze information found in the resume.

Give practical suggestions.

Keep the response simple and student-friendly.
"""


def ensure_data_files():
    """Create the JSON files the first time the app starts."""
    DATA_DIR.mkdir(exist_ok=True)
    for file_path in (USERS_FILE, ANALYSIS_FILE):
        if not file_path.exists():
            file_path.write_text("[]", encoding="utf-8")


def append_json(file_path, item):
    """Append one record to a JSON list while keeping the file readable."""
    ensure_data_files()
    try:
        records = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            records = []
    except (json.JSONDecodeError, OSError):
        records = []

    records.append(item)
    file_path.write_text(json.dumps(records, indent=2), encoding="utf-8")


def required_fields(data, fields):
    return [field for field in fields if not str(data.get(field, "")).strip()]


def generate_ai_response(prompt):
    """Send a prompt to Gemini and return its text response."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_api_key":
        raise RuntimeError("Gemini API key is missing. Set GEMINI_API_KEY in the environment.")

    from google import genai

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
    )
    response_text = (response.text or "").strip()
    if not response_text:
        raise RuntimeError("Gemini returned an empty response.")
    return response_text


def error_response(message, status=400):
    return jsonify({"success": False, "error": message}), status


@app.route("/")
def home():
    return render_template("index.html")


@app.post("/career")
def career():
    data = request.get_json(silent=True) or {}
    fields = [
        "name",
        "education",
        "skills",
        "experience_level",
        "career_goal",
        "target_role",
        "study_hours",
    ]
    missing = required_fields(data, fields)
    if missing:
        return error_response("Please complete all career coach fields.")

    prompt = CAREER_PROMPT.format(**{field: str(data[field]).strip() for field in fields})
    try:
        response_text = generate_ai_response(prompt)
    except RuntimeError as error:
        return error_response(str(error), 503)
    except Exception:
        app.logger.exception("Career guidance request failed")
        return error_response("The AI service is unavailable right now. Please try again.", 502)

    append_json(
        USERS_FILE,
        {
            "name": str(data["name"]).strip(),
            "education": str(data["education"]).strip(),
            "skills": str(data["skills"]).strip(),
            "experience_level": str(data["experience_level"]).strip(),
            "career_goal": str(data["career_goal"]).strip(),
            "target_role": str(data["target_role"]).strip(),
            "study_hours": str(data["study_hours"]).strip(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return jsonify({"success": True, "result": response_text})


@app.post("/resume")
def resume():
    resume_file = request.files.get("resume")
    target_role = request.form.get("target_role", "").strip()
    experience_level = request.form.get("experience_level", "").strip()

    if not resume_file or not resume_file.filename:
        return error_response("Please upload a PDF resume.")
    if not resume_file.filename.lower().endswith(".pdf"):
        return error_response("Only PDF resume files are supported.")
    if not target_role or not experience_level:
        return error_response("Please enter a target role and experience level.")

    try:
        reader = PdfReader(resume_file.stream)
        resume_text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception:
        return error_response("The PDF could not be read. Please upload a valid PDF.")

    if not resume_text:
        return error_response("This PDF does not contain readable text. Try an accessible text-based PDF.")

    prompt = RESUME_PROMPT.format(
        resume_text=resume_text[:30000],
        target_role=target_role,
        experience_level=experience_level,
    )
    try:
        response_text = generate_ai_response(prompt)
    except RuntimeError as error:
        return error_response(str(error), 503)
    except Exception:
        app.logger.exception("Resume analysis request failed")
        return error_response("The AI service is unavailable right now. Please try again.", 502)

    append_json(
        ANALYSIS_FILE,
        {
            "filename": secure_filename(resume_file.filename),
            "target_role": target_role,
            "experience_level": experience_level,
            "resume_characters": len(resume_text),
            "analysis": response_text,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return jsonify({"success": True, "result": response_text})


@app.errorhandler(413)
def request_too_large(_error):
    return error_response("The upload is too large. Please upload a PDF under 4 MB.", 413)


if __name__ == "__main__":
    ensure_data_files()
    app.run(debug=False)
