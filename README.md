# 🥗 NutriSense AI

## Problem Statement
People struggle to make healthy food choices due to lack of nutritional awareness and personalized guidance. Poor eating habits lead to obesity, diabetes, and lifestyle diseases affecting millions.

## Our Solution
NutriSense AI is a smart food and health companion that helps users track nutrition, calculate BMI, get personalized meal suggestions, and monitor daily health progress through an intuitive, visually stunning dashboard.

## ✨ Features
- **Smart Health Profile** — BMI calculator with personalized calorie & macro targets
- **Food Logger** — 60 Indian foods database with live search, nutrition preview & logging
- **AI Meal Suggestions** — Time-aware meal recommendations (breakfast/lunch/snack/dinner)
- **Health Dashboard** — Animated health score, progress bars, weekly chart, water tracker
- **Activity Tracking** — Step counter and distance display
- **Hydration Monitor** — Interactive 8-glass water tracker

## 🛠️ Tech Stack

| Layer       | Technology                          |
| ----------- | ----------------------------------- |
| Frontend    | HTML5, CSS3, Vanilla JavaScript     |
| Backend     | Python 3.11, Flask 3.0              |
| Fonts       | Google Fonts (Poppins)              |
| Icons       | Font Awesome 6.4                    |
| Images      | Unsplash (free, no API key needed)  |
| Server      | Gunicorn 21.2                       |
| Deployment  | Docker → Google Cloud Run           |

## 🚀 Setup Instructions

### Local Development
```bash
# Clone the repo
git clone <your-repo-url>
cd AMD_slingshot

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
# → Open http://localhost:8080
```

### Docker
```bash
docker build -t nutrisense-ai .
docker run -p 8080:8080 nutrisense-ai
```

### Deploy to Google Cloud Run
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

gcloud run deploy nutrisense-ai \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080
```

## 🌐 Live URL
> **Cloud Run**: _[Your Cloud Run URL here]_

## 📁 Project Structure
```
/
├── app.py                  # Flask backend — all routes & API
├── requirements.txt        # Python dependencies (Flask + Gunicorn)
├── Dockerfile              # Cloud Run container config
├── .gcloudignore           # Deployment exclusions
├── templates/
│   ├── base.html           # Base template (navbar + footer)
│   ├── index.html          # Home page (hero, features, testimonials)
│   ├── profile.html        # Health profile & BMI calculator
│   ├── log.html            # Food logger with search & logging
│   ├── suggest.html        # Time-aware meal suggestions
│   └── summary.html        # Health dashboard & analytics
├── static/
│   └── style.css           # Full design system
├── data/
│   └── foods.json          # 60 Indian foods nutrition database
└── README.md
```

## 📄 License
MIT
