import re
import tldextract
import idna
from urllib.parse import urlparse

extractor = tldextract.TLDExtract(suffix_list_urls=None)

# ---------------- SAFE TLD PATTERNS ----------------
# These multi-part suffixes are inherently institutional/trusted
SAFE_TLDS = [
    ".ac.in", ".edu.in", ".gov.in", ".nic.in",
    ".co.in", ".org.in", ".net.in", ".res.in",
    ".edu", ".gov", ".mil",
]

# ---------------- RISKY TLD PATTERNS ----------------
RISKY_TLDS = [".xyz", ".tk", ".ml", ".ga", ".cf", ".gq", ".top", ".click", ".pw"]

# ---------------- SHORTENERS ----------------
SHORTENERS = ['bit.ly', 'tinyurl', 't.co', 'goo.gl', 'ow.ly']

# ---------------- SUSPICIOUS WORDS ----------------
SUSPICIOUS_WORDS = [
    "login", "verify", "update", "secure", "account",
    "bank", "paypal", "free", "bonus", "signin",
    "confirm", "password", "credential", "ebay", "amazon-"
]


def has_safe_tld(url):
    """Return True if the URL ends with an institutionally safe TLD."""
    url_lower = url.lower()
    return any(url_lower.split("?")[0].split("/")[2].endswith(tld.lstrip("."))
               if "://" in url_lower else url_lower.endswith(tld.lstrip("."))
               for tld in SAFE_TLDS)


def check_homograph(domain):
    """
    Safely detect homograph (IDN) attacks.
    Returns 1 only if the domain contains actual non-ASCII / punycode xn-- characters.
    Plain ASCII domains should NEVER be flagged.
    """
    # Fast path: pure ASCII domain → definitely not a homograph attack
    try:
        domain.encode('ascii')
        # It's pure ASCII — check if it uses punycode xn-- prefix (real IDN)
        if "xn--" in domain.lower():
            return 1
        return 0
    except UnicodeEncodeError:
        # Non-ASCII characters present → likely homograph
        return 1


def extract_features(url):
    try:
        url = url.strip().lower()

        parsed = urlparse(url)
        ext = extractor(url)

        domain = ext.domain or ""
        suffix = ext.suffix or ""
        subdomain = ext.subdomain or ""

        full_domain = domain + "." + suffix if suffix else domain
        full_domain_with_sub = ".".join(
            part for part in [subdomain, domain, suffix] if part
        )

        # ---------------- BASIC ----------------
        url_length = len(url)
        domain_length = len(full_domain)
        subdomain_length = len(subdomain)

        # ---------------- CHARACTER FEATURES ----------------
        count_dot       = url.count('.')
        count_hyphen    = url.count('-')
        count_at        = url.count('@')
        count_question  = url.count('?')
        count_percent   = url.count('%')
        count_equal     = url.count('=')
        count_http      = url.count('http')
        count_https     = url.count('https')
        count_www       = url.count('www')

        # ---------------- SECURITY FEATURES ----------------
        has_ip         = 1 if re.search(r'(\d+\.){3}\d+', url) else 0
        has_https      = 1 if url.startswith("https") else 0
        has_port       = 1 if re.search(r':\d{2,5}', parsed.netloc) else 0
        has_at_symbol  = 1 if '@' in url else 0

        # ---------------- SUSPICIOUS PATTERNS ----------------
        suspicious_count = sum(word in url for word in SUSPICIOUS_WORDS)

        # ---------------- TLD RISK ----------------
        risky_tld_flag = 1 if any(url.endswith(tld) or (tld + "/") in url or (tld + "?") in url
                                  for tld in RISKY_TLDS) else 0

        # Safe TLD bonus (institutional domains)
        safe_tld_flag = 1 if any(
            full_domain_with_sub.endswith(tld.lstrip("."))
            for tld in SAFE_TLDS
        ) else 0

        # ---------------- SHORT URL ----------------
        is_short = 1 if any(s in url for s in SHORTENERS) else 0

        # ---------------- HOMOGRAPH ATTACK (FIXED) ----------------
        homograph = check_homograph(domain)

        # ---------------- PATH FEATURES ----------------
        path        = parsed.path or ""
        path_length = len(path)
        path_depth  = path.count('/')

        # ---------------- DOMAIN FEATURES ----------------
        digit_in_domain = sum(c.isdigit() for c in domain)
        alpha_in_domain = sum(c.isalpha() for c in domain)

        # ---------------- RATIO FEATURES ----------------
        digit_ratio   = digit_in_domain / (len(domain) + 1)
        special_ratio = sum(not c.isalnum() for c in url) / (len(url) + 1)

        # ---------------- FINAL FEATURE VECTOR ----------------
        features = {
            "url_length":       url_length,
            "domain_length":    domain_length,
            "subdomain_length": subdomain_length,

            "count_dot":      count_dot,
            "count_hyphen":   count_hyphen,
            "count_at":       count_at,
            "count_question": count_question,
            "count_percent":  count_percent,
            "count_equal":    count_equal,

            "count_http":  count_http,
            "count_https": count_https,
            "count_www":   count_www,

            "has_ip":        has_ip,
            "has_https":     has_https,
            "has_port":      has_port,
            "has_at_symbol": has_at_symbol,

            "suspicious_words": suspicious_count,
            "risky_tld":        risky_tld_flag,
            "safe_tld":         safe_tld_flag,        # NEW: institutional TLD bonus
            "is_short":         is_short,
            "homograph":        homograph,

            "path_length": path_length,
            "path_depth":  path_depth,

            "digit_in_domain": digit_in_domain,
            "alpha_in_domain": alpha_in_domain,

            "digit_ratio":   digit_ratio,
            "special_ratio": special_ratio,
        }

        return features

    except Exception:
        # Fallback: all-zero safe vector
        return {key: 0 for key in [
            "url_length", "domain_length", "subdomain_length",
            "count_dot", "count_hyphen", "count_at", "count_question",
            "count_percent", "count_equal", "count_http", "count_https",
            "count_www", "has_ip", "has_https", "has_port", "has_at_symbol",
            "suspicious_words", "risky_tld", "safe_tld", "is_short", "homograph",
            "path_length", "path_depth", "digit_in_domain",
            "alpha_in_domain", "digit_ratio", "special_ratio",
        ]}