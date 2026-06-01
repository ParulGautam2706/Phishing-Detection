from flask import Flask, request, jsonify, render_template
import pickle, os, re, traceback, time
import unicodedata
import pandas as pd
import requests
import tldextract
from difflib import SequenceMatcher
from urllib.parse import urlparse
from functools import lru_cache

# Import your feature extraction module
from utils.feature_extraction import extract_features

app = Flask(__name__)

# ---------------- LOAD MODEL ----------------
base = os.path.dirname(os.path.abspath(__file__))

model = pickle.load(open(os.path.join(base, "model/best_model.pkl"), "rb"))
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
    "myntra.com",
    "hdfcbank.com",
    "icicibank.com",
    "axisbank.com",
    "canarabank.com",
    "unionbankofindia.co.in",
    "bankofbaroda.in",
    "ucobank.com",
    "bankofindia.co.in",
    "centralbankofindia.co.in",
    "yesbank.in",
    "indusind.com",
    "kotak.com",
    "onlinesbi.sbi"
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

@lru_cache(maxsize=1000)
def get_full_domain(url: str) -> str:
    """Extract full domain from URL with caching"""
    try:
        ext = extractor(url)
        return ".".join(part for part in [ext.subdomain, ext.domain, ext.suffix] if part)
    except Exception:
        return ""

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

def is_typosquatting(url: str, trusted_domains: list, threshold: float = 0.85) -> tuple[bool, str]:
    """
    Detect if domain is typosquatting a trusted domain
    Returns (is_typosquatting, reason)
    """
    try:
        full_domain = get_full_domain(url)
        if not full_domain:
            return False, ""
        
        # Extract main domain (remove subdomains for better comparison)
        parts = full_domain.split('.')
        if len(parts) >= 2:
            main_domain = '.'.join(parts[-2:])  # Get domain.tld
        else:
            main_domain = full_domain
        
        for trusted in trusted_domains:
            # Skip if it's actually the trusted domain
            if main_domain == trusted:
                continue
            
            # Calculate similarity
            ratio = SequenceMatcher(None, main_domain, trusted).ratio()
            if ratio >= threshold:
                return True, f"Typosquatting: '{main_domain}' is {ratio*100:.1f}% similar to trusted domain '{trusted}'"
        
        return False, ""
    except Exception:
        return False, ""

def is_trusted(url: str) -> tuple[bool, str]:
    """
    Check if URL is from trusted domain
    Returns (is_trusted, reason)
    """
    try:
        full = get_full_domain(url)
        if not full:
            return False, ""
            
        # Check exact matches
        for t in TRUSTED_DOMAINS:
            if full == t:
                return True, f"exact match with '{t}'"
            if full.endswith("." + t):
                return True, f"subdomain match with '{t}'"
        
        # Check institutional TLDs
        for tld in INSTITUTIONAL_TLDS:
            if full.endswith(tld.lstrip(".")):
                return True, f"institutional TLD match with '{tld}'"
                
        return False, ""
    except Exception:
        return False, ""

def normalize_url(url: str) -> str:
    """Normalize URL for analysis"""
    url = url.strip()
    if not re.match(r'^https?://', url, re.IGNORECASE):
        url = "http://" + url
    return url.lower()

def expand_url(url: str) -> str:
    """Expand shortened URLs"""
    try:
        # Security check: only expand http/https URLs
        parsed = urlparse(url)
        if parsed.scheme not in ['http', 'https']:
            return url
        
        # Don't expand internal/local URLs to prevent SSRF
        hostname = parsed.hostname or ""
        if hostname in ['localhost', '127.0.0.1', '0.0.0.0']:
            return url
            
        r = requests.get(url, timeout=5, allow_redirects=True)
        return r.url
    except Exception:
        return url

def validate_url_safety(url: str) -> tuple[bool, str]:
    """
    Validate URL is safe to process
    Returns (is_safe, reason)
    """
    try:
        parsed = urlparse(url)
        
        # Check scheme
        if parsed.scheme not in ['http', 'https', '']:
            return False, f"Unsafe URL scheme: {parsed.scheme}"
        
        # Block excessively long URLs
        if len(url) > 2000:
            return False, "URL exceeds maximum length (2000 chars)"
        
        return True, ""
    except Exception as e:
        return False, f"URL parsing error: {str(e)}"

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
        url = data.get("url", "").strip()

        if not url:
            return jsonify({
                "risk": 0, 
                "result": "Invalid URL ❌", 
                "reasons": ["No URL provided"],
                "url": "",
                "ml_score": 0,
                "rule_score": 0,
                "time": "0s"
            })

        print("\n" + "="*60)
        print("🔍 Input URL:", url)

        # ---------------- SAFETY VALIDATION ----------------
        is_safe, safety_reason = validate_url_safety(url)
        if not is_safe:
            print(f"❌ Safety check failed: {safety_reason}")
            return jsonify({
                "url": url,
                "risk": 100,
                "result": "Phishing ❌",
                "ml_score": 100,
                "rule_score": 100,
                "reasons": [safety_reason],
                "time": f"{round(time.time() - start, 3)}s",
            })

        # ---------------- HOMOGRAPH CHECK ----------------
        # Must run on RAW URL before any lowercasing
        is_homo, homo_reason = detect_homograph_in_url(url)
        
        if is_homo:
            elapsed = round(time.time() - start, 3)
            print("🚨 Homograph detected:", homo_reason)
            return jsonify({
                "url": url,
                "risk": 95,
                "result": "Phishing ❌",
                "ml_score": 95,
                "rule_score": 50,
                "reasons": [f"Homograph/Unicode spoofing — {homo_reason}"],
                "time": f"{elapsed}s",
            })

        # ---------------- NORMALIZE URL ----------------
        url = normalize_url(url)
        print("🌐 Normalized URL:", url)

        # ---------------- SHORTENER EXPANSION ----------------
        if any(s in url for s in SHORTENERS):
            original_url = url
            url = expand_url(url)
            if url != original_url:
                print("🔗 Expanded to:", url)

        # ---------------- TYPOSQUATTING CHECK ----------------
        is_typo, typo_reason = is_typosquatting(url, TRUSTED_DOMAINS)
        if is_typo:
            elapsed = round(time.time() - start, 3)
            print("🚨 Typosquatting detected:", typo_reason)
            return jsonify({
                "url": url,
                "risk": 85,
                "result": "Phishing ❌",
                "ml_score": 80,
                "rule_score": 85,
                "reasons": [typo_reason],
                "time": f"{elapsed}s",
            })

        # ---------------- TRUSTED DOMAIN CHECK ----------------
        is_trusted_flag, trust_reason = is_trusted(url)
        if is_trusted_flag:
            elapsed = round(time.time() - start, 3)
            print("✅ Trusted domain:", trust_reason)
            return jsonify({
                "url": url,
                "risk": 0,
                "result": "Legitimate ✅",
                "ml_score": 0,
                "rule_score": 0,
                "reasons": [f"Trusted / institutional domain ({trust_reason})"],
                "time": f"{elapsed}s",
            })

        # ---------------- FEATURE EXTRACTION + ML ----------------
        try:
            features = extract_features(url)
            df = pd.DataFrame([features])
            df = df.reindex(columns=feature_names, fill_value=0)
            
            prob = model.predict_proba(df)[0][1]
            ml_risk = int(prob * 100)
            print("🤖 ML Risk:", ml_risk)
        except Exception as e:
            print(f"❌ Feature extraction/ML error: {e}")
            traceback.print_exc()
            # Fallback to rule-based only
            ml_risk = 50
            print("⚠️  Using fallback ML score: 50")

        # ---------------- RULE ENGINE ----------------
        rule = 0
        reasons = []

        has_ip = bool(re.search(r'(\d+\.){3}\d+', url))
        has_keywords = bool(re.search(r"(login|verify|secure|account|bank|update|confirm|password|credential|signin|auth|authenticate)", url, re.IGNORECASE))
        has_at = "@" in url
        has_encoding = bool(re.search(r'%[0-9a-f]{2}', url, re.IGNORECASE))
        many_hyphens = url.count('-') > 3
        many_dots = url.count('.') > 5
        is_https = url.startswith("https")
        has_double_slash = url.count('//') > 1
        has_suspicious_tld = any(url.endswith(tld) for tld in ['.tk', '.ml', '.ga', '.cf', '.xyz', '.top', '.club'])

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

        if has_double_slash:
            rule += 5
            reasons.append("Multiple slashes in URL")

        if has_suspicious_tld:
            rule += 15
            reasons.append(f"Suspicious TLD detected")

        if is_https:
            rule -= 2

        if len(url) < 60:
            rule -= 10

        if url.count('.') <= 3:
            rule -= 5

        # Note: safe_tld would come from features, but we can approximate
        if any(url.endswith(tld.lstrip(".")) for tld in INSTITUTIONAL_TLDS):
            rule -= 20
            reasons.append("Institutional TLD (.ac.in / .gov.in etc.)")

        print("📏 Rule Score:", rule)

        # ---------------- FINAL RISK CALCULATION ----------------
        # Weighted blend of ML + rule
        risk = int(0.85 * ml_risk + 0.15 * max(rule, 0))
        risk = max(0, min(100, risk))

        # ---------------- SUSPICIOUS DAMPENING ----------------
        # If ML thinks it's risky but no hard signals, reduce confidence
        hard_signal_count = sum([has_ip, has_keywords, has_at, has_encoding])
        
        if ml_risk >= 60 and hard_signal_count == 0:
            # No confirmed hard signals → Suspicious at most, not phishing
            risk = min(risk, 60)
            if not any("Typosquatting" in r for r in reasons):
                reasons.append("Pattern looks unusual but no confirmed phishing signals")

        # ---------------- FINAL LABEL ----------------
        # 0-20: Legitimate
        # 21-60: Suspicious
        # 61-100: Phishing
        
        if risk <= 20:
            label = "Legitimate ✅"
        elif risk <= 60:
            label = "Suspicious ⚠️"
        else:
            label = "Phishing ❌"

        # Ensure reasons are unique
        reasons = list(dict.fromkeys(reasons))
        
        elapsed = round(time.time() - start, 3)
        print(f"⚠️  Final Risk: {risk}% → {label}")
        print("="*60)

        return jsonify({
            "url": url,
            "risk": risk,
            "result": label,
            "ml_score": ml_risk,
            "rule_score": rule,
            "reasons": reasons if reasons else ["No obvious phishing indicators detected"],
            "time": f"{elapsed}s",
        })

    except Exception as e:
        print("❌ ERROR:", e)
        traceback.print_exc()
        return jsonify({
            "risk": 0, 
            "result": "Server Error ❌", 
            "reasons": [f"Internal server error: {str(e)}"],
            "url": "",
            "ml_score": 0,
            "rule_score": 0,
            "time": "0s"
        })

# ---------------- ERROR HANDLERS ----------------

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)  # Set debug=False for production