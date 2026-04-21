"""
NutriSense AI — Smart Food & Health Companion
Flask backend for the NutriSense AI project.
"""

import json
import os
from datetime import datetime
from flask import Flask, render_template, request, session, jsonify

app = Flask(__name__)
app.secret_key = "nutrisense2026"

# Load foods database
with open(os.path.join(os.path.dirname(__file__), "data", "foods.json"), "r", encoding="utf-8") as f:
    FOODS_DB = json.load(f)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/profile", methods=["GET", "POST"])
def profile():
    result = None
    if request.method == "POST":
        try:
            name = request.form.get("name", "User")
            w = float(request.form["weight"])
            h = float(request.form["height"])
            age = int(request.form["age"])
            goal = request.form.get("goal", "maintain")
            activity = request.form.get("activity", "moderate")

            bmi = round(w / (h / 100) ** 2, 1)

            # Mifflin-St Jeor
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

            # Tips based on goal
            tips_map = {
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
            session["target_cal"] = cal
            session["profile"] = result
            session["protein_target"] = protein
            session["carbs_target"] = carbs
            session["fat_target"] = fat
            session["user_name"] = name
        except (ValueError, KeyError) as e:
            result = {"error": str(e)}

    return render_template("profile.html", result=result)


@app.route("/log", methods=["GET", "POST"])
def log():
    log_list = session.get("food_log", [])

    if request.method == "POST":
        food = request.form.get("food", "").lower().strip()
        qty = float(request.form.get("qty", 100))

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
def api_foods():
    """Return foods list for JS autocomplete."""
    return jsonify(FOODS_DB)


@app.route("/clear-log")
def clear_log():
    session.pop("food_log", None)
    return render_template(
        "log.html",
        foods=FOODS_DB,
        log=[],
        total_cal=0,
        target=session.get("target_cal", 2000),
    )


@app.route("/suggest")
def suggest():
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
def summary():
    log_list = session.get("food_log", [])
    target = session.get("target_cal", 2000)
    total_cal = sum(x["cal"] for x in log_list)
    total_protein = round(sum(x["protein"] for x in log_list), 1)
    total_carbs = round(sum(x["carbs"] for x in log_list), 1)
    total_fat = round(sum(x["fat"] for x in log_list), 1)

    # Health score: based on how close to target (100 = on target)
    if target > 0:
        ratio = total_cal / target
        if ratio <= 1:
            score = int(ratio * 100)
        else:
            score = max(0, int(100 - (ratio - 1) * 50))
    else:
        score = 0

    protein_target = session.get("protein_target", 50)
    carbs_target = session.get("carbs_target", 250)
    fat_target = session.get("fat_target", 55)
    water = session.get("water", 0)
    user_name = session.get("user_name", "Champion")

    return render_template(
        "summary.html",
        total_cal=total_cal,
        target=target,
        score=score,
        log=log_list,
        protein=total_protein,
        carbs=total_carbs,
        fat=total_fat,
        protein_target=protein_target,
        carbs_target=carbs_target,
        fat_target=fat_target,
        water=water,
        user_name=user_name,
    )


@app.route("/update-water", methods=["POST"])
def update_water():
    data = request.get_json(silent=True) or {}
    session["water"] = int(data.get("count", 0))
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
