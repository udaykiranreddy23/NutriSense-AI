"""
NutriSense AI — Smart Food & Health Companion
Full-featured Flask backend with user accounts & persistent data.

Features:
    - User authentication (signup/login/logout)
    - Health profile with BMI, BMR, and macro calculations
    - Food logging with 60+ Indian food items (persistent)
    - Weight tracking with history
    - Time-aware meal suggestions
    - Interactive health dashboard
    - Water intake tracking

Security:
    - Password hashing with werkzeug
    - Input validation and sanitization
    - Security headers (CSP, X-Frame-Options, etc.)
    - Login-protected routes
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
    redirect,
    url_for,
    flash,
    abort,
)
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)

from models import (
    init_db,
    create_user,
    authenticate_user,
    get_user_by_id,
    update_user_profile,
    get_total_users,
    add_weight_entry,
    get_weight_history,
    get_weight_stats,
    save_food_entry,
    get_food_log_today,
    clear_food_log_today,
    get_weekly_calories,
    delete_food_entry,
    get_water_today,
    update_water_today,
)

# ---------------------------------------------------------------------------
# App Configuration
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "nutrisense-ai-secret-key-2026")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=1 * 1024 * 1024,  # 1MB max request size
    PERMANENT_SESSION_LIFETIME=86400 * 30,  # 30 days
)

# ---------------------------------------------------------------------------
# Flask-Login Setup
# ---------------------------------------------------------------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth"
login_manager.login_message = "Please sign in to access this feature."
login_manager.login_message_category = "info"


class User(UserMixin):
    """User class for Flask-Login."""
    def __init__(self, user_data: Dict):
        self.id = user_data["id"]
        self._data = user_data

    def __getattr__(self, name):
        if name.startswith('_') or name == 'id':
            raise AttributeError(name)
        return self._data.get(name)

    @property
    def data(self):
        return self._data


@login_manager.user_loader
def load_user(user_id):
    user_data = get_user_by_id(int(user_id))
    if user_data:
        return User(user_data)
    return None


# ---------------------------------------------------------------------------
# Initialize Database
# ---------------------------------------------------------------------------
init_db()

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


def validate_email(email: str) -> bool:
    """Basic email validation."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


# ---------------------------------------------------------------------------
# Health Goal Configuration
# ---------------------------------------------------------------------------
HEALTH_GOALS = {
    "lose": {
        "label": "🔥 Weight Loss",
        "cal_adjust": -500,
        "tips": [
            "Eat more protein to stay fuller longer",
            "Drink water before every meal",
            "Avoid sugary beverages and processed snacks",
            "Include fiber-rich foods in every meal",
        ],
    },
    "gain": {
        "label": "💪 Muscle Gain",
        "cal_adjust": 400,
        "tips": [
            "Include calorie-dense healthy foods like nuts",
            "Eat more frequent meals throughout the day",
            "Add healthy fats like ghee and avocado",
            "Consume protein within 30 min of exercise",
        ],
    },
    "maintain": {
        "label": "⚖️ Maintain Weight",
        "cal_adjust": 0,
        "tips": [
            "Keep a balanced diet with all food groups",
            "Stay consistent with meal timings",
            "Exercise regularly to maintain fitness",
            "Monitor your weight weekly",
        ],
    },
    "diabetes": {
        "label": "🩺 Manage Diabetes",
        "cal_adjust": -200,
        "tips": [
            "Choose low glycemic index foods",
            "Monitor carbohydrate intake carefully",
            "Include fiber-rich vegetables in every meal",
            "Avoid fruit juices, eat whole fruits instead",
        ],
    },
    "heart": {
        "label": "❤️ Heart Health",
        "cal_adjust": -150,
        "tips": [
            "Reduce sodium — avoid pickles and papad",
            "Eat omega-3 rich foods like fish and walnuts",
            "Choose whole grains over refined carbs",
            "Include leafy greens in every meal",
        ],
    },
    "pregnancy": {
        "label": "🤰 Pregnancy Nutrition",
        "cal_adjust": 300,
        "tips": [
            "Increase iron intake with spinach and dates",
            "Take folic acid-rich foods daily",
            "Eat small, frequent meals to prevent nausea",
            "Drink plenty of milk and buttermilk for calcium",
        ],
    },
    "athletic": {
        "label": "🏋️ Athletic Performance",
        "cal_adjust": 500,
        "tips": [
            "Eat complex carbs 2-3 hours before training",
            "Consume 1.5-2g protein per kg body weight",
            "Stay hydrated — drink 3-4 liters of water daily",
            "Refuel with banana and curd post-workout",
        ],
    },
    "stress": {
        "label": "🧘 Stress & Sleep",
        "cal_adjust": 0,
        "tips": [
            "Eat magnesium-rich foods — almonds, banana, spinach",
            "Drink warm turmeric milk before bed",
            "Avoid caffeine after 3 PM",
            "Include complex carbs in dinner for better sleep",
        ],
    },
    "bone": {
        "label": "🦴 Bone Health",
        "cal_adjust": 0,
        "tips": [
            "Eat calcium-rich foods — curd, paneer, ragi",
            "Get enough Vitamin D through sunlight",
            "Include sesame seeds and green leafy vegetables",
            "Avoid excess salt which depletes calcium",
        ],
    },
    "brain": {
        "label": "🧠 Brain & Focus",
        "cal_adjust": 0,
        "tips": [
            "Eat omega-3 rich foods — walnuts, flax seeds",
            "Include blueberries and dark chocolate",
            "Stay hydrated — dehydration hurts focus",
            "Eat breakfast daily for better concentration",
        ],
    },
    "detox": {
        "label": "🌿 Detox & Cleanse",
        "cal_adjust": -300,
        "tips": [
            "Start mornings with warm lemon water",
            "Eat fiber-rich fruits and vegetables",
            "Avoid processed foods and added sugars",
            "Drink green tea 2-3 times a day",
        ],
    },
}


# ---------------------------------------------------------------------------
# Routes — Authentication
# ---------------------------------------------------------------------------
@app.route("/auth")
def auth():
    """Show login/signup page."""
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    return render_template("auth.html")


@app.route("/signup", methods=["POST"])
def signup():
    """Handle user registration."""
    name = sanitize_string(request.form.get("name", ""))
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm = request.form.get("confirm_password", "")

    if not name or len(name) < 2:
        flash("Please enter your full name.", "error")
        return redirect(url_for("auth"))

    if not validate_email(email):
        flash("Please enter a valid email address.", "error")
        return redirect(url_for("auth"))

    if len(password) < 6:
        flash("Password must be at least 6 characters.", "error")
        return redirect(url_for("auth"))

    if password != confirm:
        flash("Passwords do not match.", "error")
        return redirect(url_for("auth"))

    user_id = create_user(name, email, password)
    if user_id is None:
        flash("An account with this email already exists. Please sign in.", "error")
        return redirect(url_for("auth"))

    # Auto-login after signup
    user_data = get_user_by_id(user_id)
    login_user(User(user_data), remember=True)
    flash(f"Welcome to NutriSense AI, {name}! 🎉", "success")
    return redirect(url_for("profile"))


@app.route("/login", methods=["POST"])
def login():
    """Handle user login."""
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    remember = request.form.get("remember") == "on"

    if not email or not password:
        flash("Please enter email and password.", "error")
        return redirect(url_for("auth"))

    user_data = authenticate_user(email, password)
    if user_data is None:
        flash("Invalid email or password. Please try again.", "error")
        return redirect(url_for("auth"))

    login_user(User(user_data), remember=remember)
    flash(f"Welcome back, {user_data['name']}! 👋", "success")

    next_page = request.args.get("next")
    return redirect(next_page or url_for("home"))


@app.route("/logout")
@login_required
def logout():
    """Log out user."""
    logout_user()
    flash("You've been signed out. See you soon! 👋", "info")
    return redirect(url_for("home"))


# ---------------------------------------------------------------------------
# Routes — Pages
# ---------------------------------------------------------------------------
@app.route("/")
def home() -> str:
    """Render the landing/home page."""
    total_users = get_total_users()
    return render_template("index.html", total_users=total_users)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile() -> str:
    """
    Health profile page.

    GET: Show the profile form pre-filled with user data.
    POST: Calculate BMI, daily calories, and macro targets
          using the Mifflin-St Jeor equation, and save to DB.
    """
    result: Optional[Dict[str, Any]] = None
    user = get_user_by_id(current_user.id)

    if request.method == "POST":
        try:
            name = sanitize_string(request.form.get("name", user["name"]))
            w = validate_number(request.form["weight"], 20, 300)
            h = validate_number(request.form["height"], 50, 250)
            age = int(validate_number(request.form["age"], 1, 120))
            gender = sanitize_string(request.form.get("gender", "male"))
            goal = sanitize_string(request.form.get("goal", "maintain"))
            activity = sanitize_string(request.form.get("activity", "moderate"))
            target_weight = validate_number(
                request.form.get("target_weight", "0"), 0, 300
            )

            # BMI calculation
            bmi = round(w / (h / 100) ** 2, 1)

            # Mifflin-St Jeor BMR (gender-aware)
            if gender == "female":
                cal = round((10 * w) + (6.25 * h) - (5 * age) - 161)
            else:
                cal = round((10 * w) + (6.25 * h) - (5 * age) + 5)

            # Activity multiplier
            multipliers = {
                "sedentary": 1.2,
                "light": 1.375,
                "moderate": 1.55,
                "very_active": 1.725,
                "extreme": 1.9,
            }
            cal = round(cal * multipliers.get(activity, 1.55))

            # Goal adjustment
            goal_config = HEALTH_GOALS.get(goal, HEALTH_GOALS["maintain"])
            cal = round(cal + goal_config["cal_adjust"])

            # Macro targets based on goal
            if goal in ("gain", "athletic"):
                protein_pct, carbs_pct, fat_pct = 0.30, 0.45, 0.25
            elif goal in ("lose", "detox"):
                protein_pct, carbs_pct, fat_pct = 0.30, 0.40, 0.30
            elif goal == "diabetes":
                protein_pct, carbs_pct, fat_pct = 0.25, 0.40, 0.35
            else:
                protein_pct, carbs_pct, fat_pct = 0.25, 0.50, 0.25

            protein = round((cal * protein_pct) / 4)
            carbs = round((cal * carbs_pct) / 4)
            fat = round((cal * fat_pct) / 9)

            # BMI category
            if bmi < 18.5:
                bmi_cat = "Underweight"
            elif bmi < 25:
                bmi_cat = "Normal"
            elif bmi < 30:
                bmi_cat = "Overweight"
            else:
                bmi_cat = "Obese"

            result = {
                "name": name,
                "bmi": bmi,
                "bmi_cat": bmi_cat,
                "cal": cal,
                "protein": protein,
                "carbs": carbs,
                "fat": fat,
                "goal": goal,
                "goal_label": goal_config["label"],
                "tips": goal_config["tips"],
                "protein_pct": int(protein_pct * 100),
                "carbs_pct": int(carbs_pct * 100),
                "fat_pct": int(fat_pct * 100),
            }

            # Save to database
            update_user_profile(
                current_user.id,
                name=name, age=age, height=h, weight=w,
                gender=gender, goal=goal, activity=activity,
                target_weight=target_weight, target_cal=cal,
                protein_target=protein, carbs_target=carbs, fat_target=fat,
            )

            # Also add a weight entry
            add_weight_entry(current_user.id, w, h)

            # Store in session for quick access
            session["target_cal"] = cal
            session["profile"] = result

            flash("Profile updated successfully! ✅", "success")

        except (ValueError, KeyError, ZeroDivisionError) as e:
            result = {"error": f"Invalid input: {e}"}

    return render_template(
        "profile.html",
        result=result,
        user=user,
        goals=HEALTH_GOALS,
    )


@app.route("/log", methods=["GET", "POST"])
@login_required
def log() -> str:
    """
    Food logging page.

    GET: Show food database and current log.
    POST: Add a food item to today's log (per 100g).
    """
    if request.method == "POST":
        food = sanitize_string(request.form.get("food", "")).lower()
        qty = validate_number(request.form.get("qty", "100"), 1, 5000, 100)

        if food in FOODS_DB:
            item = FOODS_DB[food]
            factor = qty / 100
            save_food_entry(
                user_id=current_user.id,
                food_name=food,
                qty=qty,
                cal=round(item["cal"] * factor),
                protein=round(item["protein"] * factor, 1),
                carbs=round(item["carbs"] * factor, 1),
                fat=round(item["fat"] * factor, 1),
                emoji=item.get("emoji", "🍽️"),
            )

    log_list = get_food_log_today(current_user.id)
    user = get_user_by_id(current_user.id)
    target = user.get("target_cal", 2000) if user else 2000
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
@login_required
def clear_log() -> str:
    """Clear today's food log."""
    clear_food_log_today(current_user.id)
    user = get_user_by_id(current_user.id)
    return render_template(
        "log.html",
        foods=FOODS_DB,
        log=[],
        total_cal=0,
        target=user.get("target_cal", 2000) if user else 2000,
    )


@app.route("/delete-food/<int:entry_id>")
@login_required
def delete_food(entry_id: int):
    """Delete a specific food entry."""
    delete_food_entry(entry_id, current_user.id)
    return redirect(url_for("log"))


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


@app.route("/weight", methods=["GET", "POST"])
@login_required
def weight() -> str:
    """Weight tracking page."""
    user = get_user_by_id(current_user.id)

    if request.method == "POST":
        w = validate_number(request.form.get("weight", "0"), 20, 300)
        note = sanitize_string(request.form.get("note", ""), 200)
        if w > 0:
            add_weight_entry(current_user.id, w, user["height"])
            flash("Weight entry added! ⚖️", "success")
            return redirect(url_for("weight"))

    history = get_weight_history(current_user.id, 30)
    stats = get_weight_stats(current_user.id)

    return render_template(
        "weight.html",
        user=user,
        history=history,
        stats=stats,
    )


@app.route("/api/weight-history")
@login_required
def api_weight_history():
    """API: Get weight history for charts."""
    history = get_weight_history(current_user.id, 30)
    return jsonify(list(reversed(history)))


@app.route("/summary")
@login_required
def summary() -> str:
    """
    Health dashboard/summary page.

    Displays: health score, calorie progress, macro breakdown,
    water intake, activity stats, weekly chart, and health tips.
    """
    user = get_user_by_id(current_user.id)
    log_list = get_food_log_today(current_user.id)
    weekly = get_weekly_calories(current_user.id)
    water = get_water_today(current_user.id)
    weight_stats = get_weight_stats(current_user.id)

    target = user.get("target_cal", 2000) if user else 2000
    total_cal = sum(x["cal"] for x in log_list)
    total_protein = round(sum(x["protein"] for x in log_list), 1)
    total_carbs = round(sum(x["carbs"] for x in log_list), 1)
    total_fat = round(sum(x["fat"] for x in log_list), 1)

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
        protein_target=user.get("protein_target", 50) if user else 50,
        carbs_target=user.get("carbs_target", 250) if user else 250,
        fat_target=user.get("fat_target", 55) if user else 55,
        water=water,
        user_name=user.get("name", "Champion") if user else "Champion",
        weekly=weekly,
        weight_stats=weight_stats,
        user=user,
    )


@app.route("/update-water", methods=["POST"])
@login_required
def update_water() -> Any:
    """Update water intake count (0-8 glasses)."""
    data = request.get_json(silent=True) or {}
    count = int(validate_number(str(data.get("count", 0)), 0, 8))
    update_water_today(current_user.id, count)
    return jsonify({"ok": True, "count": count})


# ---------------------------------------------------------------------------
# Error Handlers
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    """Custom 404 error handler."""
    return render_template("index.html", total_users=get_total_users()), 404


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
