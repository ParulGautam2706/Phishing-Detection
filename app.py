from flask import Flask, request, jsonify, render_template
import pickle, os, re, traceback, time
import unicodedata
import pandas as pd
import requests
import tldextract
from urllib.parse import urlparse

from utils.feature_extraction import extract_features

app = Flask(__name__)

# ---------------- LOAD MODEL ----------------
base = os.path.dirname(os.path.abspath(__file__))

model         = pickle.load(open(os.path.join(base, "model/best_model.pkl"), "rb"))
feature_names = pickle.load(open(os.path.join(base, "model/feature_names.pkl"), "rb"))

extractor = tldextract.TLDExtract(suffix_list_urls=None)

# ---------------- CONFIG ----------------

TRUSTED_DOMAINS = [
    "google.com",
    "microsoft.com",
    "amazon.in",
    "github.com",
    "bing.com",
    "youtube.com",
    "linkedin.com",
    "wikipedia.org",
    "sbi.co.in",
    "onlinesbi.sbi.co.in",
    "piet.co.in",
    "irctc.co.in",
    "incometax.gov.in",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "paypal.com",
    "apple.com",
    "netflix.com",
    "flipkart.com",
    "hdfcbank.com",
    "icicibank.com",
    "axisbank.com",
]

INSTITUTIONAL_TLDS = [
    ".ac.in",
    ".edu.in",
    ".gov.in",
    ".nic.in",
    ".mil",
    ".gov",
    ".edu",
    ".res.in",
    ".org.in",
]

SHORTENERS = ["bit.ly", "tinyurl", "t.co", "goo.gl", "ow.ly"]

# ---------------- HELPERS ----------------

def get_full_domain(url: str) -> str:
    ext = extractor(url)
    return ".".join(part for part in [ext.subdomain, ext.domain, ext.suffix] if part)


def detect_homograph_in_url(raw_url: str) -> tuple[bool, str]:
    """
    Detect Cyrillic/Greek/Unicode lookalike chars in hostname
    BEFORE lowercasing — must run on the raw original input.
    """
    try:
        raw = raw_url.strip()
        if not re.match(r'^https?://', raw, re.IGNORECASE):
            raw = "http://" + raw
        hostname = urlparse(raw).hostname or ""

        LOOKALIKE_CHARS = set(
            "АВСЕНІЈКМНОРРТХавсегіјкмнорртухЕ"   # Cyrillic
            "ΑΒΕΖΗΙΚΜΝΟΡΤΥΧαβεηικμνοτυχ"          # Greek
            "օ"                                      # Armenian
        )

        found = [ch for ch in hostname if ch in LOOKALIKE_CHARS]
        if found:
            return True, f"Unicode lookalike chars in domain: {''.join(set(found))}"

        non_ascii = [ch for ch in hostname if ord(ch) > 127]
        if non_ascii:
            return True, f"Non-ASCII chars in domain: {''.join(set(non_ascii))}"

        if "xn--" in hostname.lower():
            return True, "Punycode (xn--) detected in domain"

        return False, ""
    except Exception:
        return False, ""


def is_trusted(url: str) -> bool:
    try:
        full = get_full_domain(url)
        for t in TRUSTED_DOMAINS:
            if full == t or full.endswith("." + t):
                return True
        for tld in INSTITUTIONAL_TLDS:
            if full.endswith(tld.lstrip(".")):
                return True
        return False
    except Exception:
        return False


def normalize_url(url: str) -> str:
    url = url.strip()
    if not re.match(r'^https?://', url, re.IGNORECASE):
        url = "http://" + url
    return url.lower()


def expand_url(url: str) -> str:
    try:
        r = requests.get(url, timeout=5, allow_redirects=True)
        return r.url
    except Exception:
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
        data = request.get_json(force=True, silent=True) or {}
        url  = data.get("url", "").strip()

        if not url:
            return jsonify({"risk": 0, "result": "Invalid URL ❌", "reasons": []})

        print("\n🔍 Input URL:", url)

        # ------------------------------------------------------------------ #
        #  HOMOGRAPH CHECK — must run on RAW URL before any lowercasing        #
        #  Cyrillic 'а'/'о' survive .lower() unchanged — check first!         #
        # ------------------------------------------------------------------ #
        is_homo, homo_reason = detect_homograph_in_url(url)

        url = normalize_url(url)

        if any(s in url for s in SHORTENERS):
            url = expand_url(url)
            print("🔗 Expanded to:", url)

        print("🌐 Final URL:", url)

        # ------------------------------------------------------------------ #
        #  HOMOGRAPH → instant Phishing                                        #
        # ------------------------------------------------------------------ #
        if is_homo:
            elapsed = round(time.time() - start, 3)
            print("🚨 Homograph detected:", homo_reason)
            return jsonify({
                "url":        url,
                "risk":       95,
                "result":     "Phishing ❌",
                "ml_score":   95,
                "rule_score": 50,
                "reasons":    [f"Homograph/Unicode spoofing — {homo_reason}"],
                "time":       f"{elapsed}s",
            })

        # ------------------------------------------------------------------ #
        #  TRUSTED DOMAIN → instant Legitimate                                 #
        # ------------------------------------------------------------------ #
        if is_trusted(url):
            elapsed = round(time.time() - start, 3)
            print("✅ Trusted domain")
            return jsonify({
                "url":        url,
                "risk":       0,
                "result":     "Legitimate ✅",
                "ml_score":   0,
                "rule_score": 0,
                "reasons":    ["Trusted / institutional domain"],
                "time":       f"{elapsed}s",
            })

        # ------------------------------------------------------------------ #
        #  FEATURE EXTRACTION + ML                                             #
        # ------------------------------------------------------------------ #
        features = extract_features(url)
        df = pd.DataFrame([features])
        df = df.reindex(columns=feature_names, fill_value=0)

        prob    = model.predict_proba(df)[0][1]
        ml_risk = int(prob * 100)
        print("🤖 ML Risk:", ml_risk)

        # ------------------------------------------------------------------ #
        #  RULE ENGINE                                                         #
        #  Also track individual hard signals for dampening logic below        #
        # ------------------------------------------------------------------ #
        rule    = 0
        reasons = []

        has_ip       = bool(re.search(r'(\d+\.){3}\d+', url))
        has_keywords = bool(re.search(r"(login|verify|secure|account|bank|update|confirm|password|credential)", url))
        has_at       = "@" in url
        has_encoding = bool(re.search(r'%[0-9a-f]{2}', url))
        many_hyphens = url.count('-') > 3
        many_dots    = url.count('.') > 5
        is_https     = url.startswith("https")

        if has_ip:
            rule += 25
            reasons.append("IP address used instead of domain")

        if has_keywords:
            rule += 15
            reasons.append("Sensitive keywords detected")

        if has_at:
            rule += 20
            reasons.append("@ symbol in URL")

        if has_encoding:
            rule += 10
            reasons.append("URL encoding detected")

        if many_hyphens:
            rule += 10
            reasons.append("Excessive hyphens")

        if many_dots:
            rule += 10
            reasons.append("Excessive dots")

        if len(url) > 100:
            rule += 10
            reasons.append("Long URL (>100 chars)")

        if is_https:
            rule -= 10

        if len(url) < 60:
            rule -= 10

        if url.count('.') <= 3:
            rule -= 5

        if features.get("safe_tld", 0) == 1:
            rule -= 20
            reasons.append("Institutional TLD (.ac.in / .gov.in etc.)")

        print("📏 Rule Score:", rule)

        # ------------------------------------------------------------------ #
        #  FINAL RISK — weighted blend of ML + rule                            #
        # ------------------------------------------------------------------ #
        risk = int(0.85 * ml_risk + 0.15 * max(rule, 0))
        risk = max(0, min(100, risk))

        # ------------------------------------------------------------------ #
        #  SUSPICIOUS DAMPENING                                                #
        #                                                                      #
        #  The ML model is binary by nature — trained datasets push scores    #
        #  to cluster near 0–10 (legit) or 80–95 (phishing). URLs that are   #
        #  merely suspicious (odd TLD, no HTTPS, generic domain) get scored   #
        #  80+ even though they have zero confirmed attack signals.            #
        #                                                                      #
        #  We count HARD signals (IP, phishing keywords, @, encoding).        #
        #  If ML is high but hard signal count is low, we cap risk into        #
        #  the Suspicious band (21–60) instead of letting it hit Phishing.   #
        # ------------------------------------------------------------------ #
        hard_signal_count = sum([has_ip, has_keywords, has_at, has_encoding])

        if ml_risk >= 60:
            if hard_signal_count == 0:
                # No confirmed hard signals → Suspicious at most
                risk = min(risk, 45)
                if not reasons:
                    reasons.append("Pattern looks unusual but no confirmed phishing signals")
            elif hard_signal_count == 1 and is_https:
                # Only 1 weak signal and URL is HTTPS → borderline Suspicious
                risk = min(risk, 55)

        risk = max(0, min(100, risk))
        print("⚠️  Final Risk:", risk)

        # ------------------------------------------------------------------ #
        #  LABEL — 3 tiers                                                     #
        # ------------------------------------------------------------------ #
        #   0 – 20  → Legitimate   (clean URLs)
        #  21 – 60  → Suspicious   (weak/moderate signals)
        #  61 – 100 → Phishing     (strong confirmed signals)
        # ------------------------------------------------------------------ #
        if risk <= 20:
            label = "Legitimate ✅"
        elif risk <= 60:
            label = "Suspicious ⚠️"
        else:
            label = "Phishing ❌"

        return jsonify({
            "url":        url,
            "risk":       risk,
            "result":     label,
            "ml_score":   ml_risk,
            "rule_score": rule,
            "reasons":    reasons,
            "time":       f"{round(time.time() - start, 3)}s",
        })

    except Exception as e:
        print("❌ ERROR:", e)
        traceback.print_exc()
        return jsonify({"risk": 0, "result": "Server Error ❌", "reasons": []})


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)