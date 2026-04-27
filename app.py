from flask import Flask, request, jsonify, render_template
import pickle, os, re, traceback, time
import pandas as pd
import requests
import tldextract

from utils.feature_extraction import extract_features

app = Flask(__name__)

# ---------------- LOAD ----------------
base = os.path.dirname(os.path.abspath(__file__))

model = pickle.load(open(os.path.join(base, "model/best_model.pkl"), "rb"))
feature_names = pickle.load(open(os.path.join(base, "model/feature_names.pkl"), "rb"))

extractor = tldextract.TLDExtract(suffix_list_urls=None)

# ---------------- CONFIG ----------------
TRUSTED = [
    "google.com",
    "microsoft.com",
    "amazon.in",
    "github.com",
    "bing.com",
    "sbi.bank.in",
    "onlinesbi.sbi.bank.in",
    "piet.co.in"
]

SHORTENERS = ["bit.ly", "tinyurl", "t.co", "goo.gl", "ow.ly"]

# ---------------- UTILS ----------------
def is_trusted(url):
    try:
        ext = extractor(url)

        full_domain = ".".join(
            part for part in [ext.subdomain, ext.domain, ext.suffix] if part
        )

        for t in TRUSTED:
            if full_domain.endswith(t):
                return True
        return False
    except:
        return False


def normalize_url(url):
    if not url.startswith("http"):
        url = "http://" + url
    return url.lower().strip()


def expand_url(url):
    try:
        return requests.get(url, timeout=4, allow_redirects=True).url
    except:
        return url


# ---------------- ROUTES ----------------
@app.route('/')
def home():
    return render_template("index.html")


@app.route('/about')
def about():
    return render_template("about.html")


@app.route('/contact')
def contact():
    return render_template("contact.html")


# ---------------- PREDICT ----------------
@app.route('/predict', methods=['POST'])
def predict():
    start = time.time()

    try:
        data = request.get_json()
        url = data.get("url", "").strip()

        if not url:
            return jsonify({"risk": 0, "result": "Invalid URL ❌"})

        print("\n🔍 Input URL:", url)

        # Normalize
        url = normalize_url(url)

        # Expand short links
        if any(s in url for s in SHORTENERS):
            url = expand_url(url)

        print("🌐 Final URL:", url)

        # ---------------- FEATURES ----------------
        features = extract_features(url)
        df = pd.DataFrame([features])

        # Align features
        df = df.reindex(columns=feature_names, fill_value=0)

        # ---------------- ML ----------------
        prob = model.predict_proba(df)[0][1]
        ml_risk = int(prob * 100)

        print("ML Risk:", ml_risk)

        # ---------------- RULE ENGINE ----------------
        rule = 0
        reasons = []

        # BAD signals
        if len(url) > 100:
            rule += 10
            reasons.append("Long URL")

        if re.search(r'(\d+\.){3}\d+', url):
            rule += 25
            reasons.append("IP address used")

        if re.search(r"(login|verify|secure|account|bank|update)", url):
            rule += 15
            reasons.append("Sensitive keywords")

        if "@" in url:
            rule += 20
            reasons.append("@ symbol")

        if url.count('-') > 3:
            rule += 10

        if url.count('.') > 4:
            rule += 10

        # GOOD signals (IMPORTANT FIX)
        if url.startswith("https"):
            rule -= 10

        if len(url) < 60:
            rule -= 10

        if url.count('.') <= 3:
            rule -= 5

        print("Rule Score:", rule)

        # ---------------- FINAL RISK ----------------
        risk = int(0.9 * ml_risk + 0.1 * rule)

        # TRUSTED DOMAIN FIX
        if is_trusted(url):
            risk = max(0, risk - 80)
            reasons.append("Trusted domain")

        risk = max(0, min(100, risk))

        print("Final Risk:", risk)

        # ---------------- FINAL LABEL ----------------
        if risk <= 15:
            label = "Legitimate ✅"
        elif risk <= 55:
            label = "Suspicious ⚠️"
        else:
            label = "Phishing ❌"

        return jsonify({
            "url": url,
            "risk": risk,
            "result": label,
            "ml_score": ml_risk,
            "rule_score": rule,
            "reasons": reasons,
            "time": f"{round(time.time() - start, 3)}s"
        })

    except Exception as e:
        print("❌ ERROR:", e)
        traceback.print_exc()
        return jsonify({"risk": 0, "result": "Server Error ❌"})


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)