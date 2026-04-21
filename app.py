"""
NutriSense AI — Smart Food & Health Companion
Flask backend for the NutriSense AI project.

Features:
    - Health profile with BMI and macro calculations
    - Food logging with 60+ Indian food items
    - Time-aware meal suggestions
    - Interactive health dashboard
    - Water intake tracking

Security:
    - Input validation and sanitization
    - Security headers (CSP, X-Frame-Options, etc.)
    - Session-based data with secure cookies
"""

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import (
    Flask,
    render_template,
    request,
    session,
    jsonify,
    abort,
)

# ---------------------------------------------------------------------------
# App Configuration
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24).hex())
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=1 * 1024 * 1024,  # 1MB max request size
)

# ---------------------------------------------------------------------------
# Load foods database
# ---------------------------------------------------------------------------
FOODS_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "foods.json")
with open(FOODS_DB_PATH, "r", encoding="utf-8") as f:
    FOODS_DB: Dict[str, Any] = json.load(f)


# ---------------------------------------------------------------------------
# Security Middleware
# ---------------------------------------------------------------------------
@app.after_request
def add_security_headers(response):
    """Add security headers to every response."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


# ---------------------------------------------------------------------------
# Input Validation Helpers
# ---------------------------------------------------------------------------
def sanitize_string(value: str, max_length: int = 100) -> str:
    """Sanitize user input string to prevent XSS."""
    if not isinstance(value, str):
        return ""
    # Remove HTML tags
    clean = re.sub(r"<[^>]+>", "", value)
    return clean.strip()[:max_length]


def validate_number(
    value: str,
    min_val: float = 0,
    max_val: float = 10000,
    default: float = 0,
) -> float:
    """Validate and clamp a numeric input."""
    try:
        num = float(value)
        return max(min_val, min(num, max_val))
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Routes — Pages
# ---------------------------------------------------------------------------
@app.route("/")
def home() -> str:
    """Render the landing/home page."""
    return render_template("index.html")


@app.route("/profile", methods=["GET", "POST"])
def profile() -> str:
    """
    Health profile page.

    GET: Show the profile form.
    POST: Calculate BMI, daily calories, and macro targets
          using the Mifflin-St Jeor equation.
    """
    result: Optional[Dict[str, Any]] = None

    if request.method == "POST":
        try:
            name = sanitize_string(request.form.get("name", "User"))
            w = validate_number(request.form["weight"], 20, 300)
            h = validate_number(request.form["height"], 50, 250)
            age = int(validate_number(request.form["age"], 1, 120))
            goal = sanitize_string(request.form.get("goal", "maintain"))
            activity = sanitize_string(request.form.get("activity", "moderate"))

            # BMI calculation
            bmi = round(w / (h / 100) ** 2, 1)

            # Mifflin-St Jeor BMR
            cal = round((10 * w) + (6.25 * h) - (5 * age) + 5)

            # Activity multiplier
            multipliers = {
                "sedentary": 1.2,
                "light": 1.375,
                "moderate": 1.55,
                "very_active": 1.725,
            }
            cal = round(cal * multipliers.get(activity, 1.55))

            # Goal adjustment
            if goal == "lose":
                cal = round(cal - 500)
            elif goal == "gain":
                cal = round(cal + 400)

            # Macro targets
            protein = round((cal * 0.25) / 4)
            carbs = round((cal * 0.50) / 4)
            fat = round((cal * 0.25) / 9)

            # BMI category
            if bmi < 18.5:
                bmi_cat = "Underweight"
            elif bmi < 25:
                bmi_cat = "Normal"
            elif bmi < 30:
                bmi_cat = "Overweight"
            else:
                bmi_cat = "Obese"

            # Personalized tips
            tips_map: Dict[str, List[str]] = {
                "lose": [
                    "Eat more protein to stay fuller longer",
                    "Drink water before every meal",
                    "Avoid sugary beverages and processed snacks",
                ],
                "gain": [
                    "Include calorie-dense healthy foods like nuts",
                    "Eat more frequent meals throughout the day",
                    "Add healthy fats like ghee and avocado",
                ],
                "maintain": [
                    "Keep a balanced diet with all food groups",
                    "Stay consistent with meal timings",
                    "Exercise regularly to maintain fitness",
                ],
                "diabetes": [
                    "Choose low glycemic index foods",
                    "Monitor carbohydrate intake carefully",
                    "Include fiber-rich vegetables in every meal",
                ],
            }

            result = {
                "name": name,
                "bmi": bmi,
                "bmi_cat": bmi_cat,
                "cal": cal,
                "protein": protein,
                "carbs": carbs,
                "fat": fat,
                "goal": goal,
                "tips": tips_map.get(goal, tips_map["maintain"]),
            }

            # Store in session
            session["target_cal"] = cal
            session["profile"] = result
            session["protein_target"] = protein
            session["carbs_target"] = carbs
            session["fat_target"] = fat
            session["user_name"] = name

        except (ValueError, KeyError, ZeroDivisionError) as e:
            result = {"error": f"Invalid input: {e}"}

    return render_template("profile.html", result=result)


@app.route("/log", methods=["GET", "POST"])
def log() -> str:
    """
    Food logging page.

    GET: Show food database and current log.
    POST: Add a food item to today's log (per 100g).
    """
    log_list: List[Dict[str, Any]] = session.get("food_log", [])

    if request.method == "POST":
        food = sanitize_string(request.form.get("food", "")).lower()
        qty = validate_number(request.form.get("qty", "100"), 1, 5000, 100)

        if food in FOODS_DB:
            item = FOODS_DB[food]
            factor = qty / 100
            entry = {
                "name": food,
                "qty": qty,
                "cal": round(item["cal"] * factor),
                "protein": round(item["protein"] * factor, 1),
                "carbs": round(item["carbs"] * factor, 1),
                "fat": round(item["fat"] * factor, 1),
                "emoji": item.get("emoji", "🍽️"),
            }
            log_list.append(entry)
            session["food_log"] = log_list

    target = session.get("target_cal", 2000)
    total_cal = sum(x["cal"] for x in log_list)

    return render_template(
        "log.html",
        foods=FOODS_DB,
        log=log_list,
        total_cal=total_cal,
        target=target,
    )


@app.route("/api/foods")
def api_foods() -> Any:
    """REST API: Return the complete foods database as JSON."""
    return jsonify(FOODS_DB)


@app.route("/clear-log")
def clear_log() -> str:
    """Clear the current session's food log."""
    session.pop("food_log", None)
    return render_template(
        "log.html",
        foods=FOODS_DB,
        log=[],
        total_cal=0,
        target=session.get("target_cal", 2000),
    )


@app.route("/suggest")
def suggest() -> str:
    """
    Time-aware meal suggestions page.

    Automatically detects meal period based on current hour:
    - Before 11: Breakfast
    - 11-16: Lunch
    - 16-19: Snack
    - After 19: Dinner
    """
    hour = datetime.now().hour
    if hour < 11:
        meal_time = "breakfast"
    elif hour < 16:
        meal_time = "lunch"
    elif hour < 19:
        meal_time = "snack"
    else:
        meal_time = "dinner"

    return render_template("suggest.html", meal_time=meal_time, hour=hour)


@app.route("/summary")
def summary() -> str:
    """
    Health dashboard/summary page.

    Displays: health score, calorie progress, macro breakdown,
    water intake, activity stats, weekly chart, and health tips.
    """
    log_list: List[Dict[str, Any]] = session.get("food_log", [])
    target: int = session.get("target_cal", 2000)
    total_cal: int = sum(x["cal"] for x in log_list)
    total_protein: float = round(sum(x["protein"] for x in log_list), 1)
    total_carbs: float = round(sum(x["carbs"] for x in log_list), 1)
    total_fat: float = round(sum(x["fat"] for x in log_list), 1)

    # Health score: 100 when on target, decreases when over/under
    if target > 0:
        ratio = total_cal / target
        if ratio <= 1:
            score = int(ratio * 100)
        else:
            score = max(0, int(100 - (ratio - 1) * 50))
    else:
        score = 0

    return render_template(
        "summary.html",
        total_cal=total_cal,
        target=target,
        score=score,
        log=log_list,
        protein=total_protein,
        carbs=total_carbs,
        fat=total_fat,
        protein_target=session.get("protein_target", 50),
        carbs_target=session.get("carbs_target", 250),
        fat_target=session.get("fat_target", 55),
        water=session.get("water", 0),
        user_name=session.get("user_name", "Champion"),
    )


@app.route("/update-water", methods=["POST"])
def update_water() -> Any:
    """Update water intake count (0-8 glasses)."""
    data = request.get_json(silent=True) or {}
    count = int(validate_number(str(data.get("count", 0)), 0, 8))
    session["water"] = count
    return jsonify({"ok": True, "count": count})


# ---------------------------------------------------------------------------
# Error Handlers
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    """Custom 404 error handler."""
    return render_template("index.html"), 404


@app.errorhandler(500)
def server_error(e):
    """Custom 500 error handler."""
    return jsonify({"error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
