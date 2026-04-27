import re
import tldextract
import idna
from urllib.parse import urlparse

extractor = tldextract.TLDExtract(suffix_list_urls=None)

def extract_features(url):
    try:
        url = url.strip().lower()

        parsed = urlparse(url)
        ext = extractor(url)

        domain = ext.domain
        suffix = ext.suffix
        subdomain = ext.subdomain

        full_domain = domain + "." + suffix if suffix else domain

        # ---------------- BASIC ----------------
        url_length = len(url)
        domain_length = len(full_domain)
        subdomain_length = len(subdomain)

        # ---------------- CHARACTER FEATURES ----------------
        count_dot = url.count('.')
        count_hyphen = url.count('-')
        count_at = url.count('@')
        count_question = url.count('?')
        count_percent = url.count('%')
        count_equal = url.count('=')
        count_http = url.count('http')
        count_https = url.count('https')
        count_www = url.count('www')

        # ---------------- SECURITY FEATURES ----------------
        has_ip = 1 if re.search(r'(\d+\.){3}\d+', url) else 0
        has_https = 1 if url.startswith("https") else 0
        has_port = 1 if ":" in parsed.netloc else 0
        has_at_symbol = 1 if '@' in url else 0

        # ---------------- SUSPICIOUS PATTERNS ----------------
        suspicious_words = [
            "login","verify","update","secure","account",
            "bank","paypal","free","bonus","signin"
        ]

        suspicious_count = sum(word in url for word in suspicious_words)

        # ---------------- TLD RISK ----------------
        risky_tlds = [".xyz", ".tk", ".ml", ".ga", ".cf", ".gq"]
        risky_tld_flag = 1 if any(tld in url for tld in risky_tlds) else 0

        # ---------------- SHORT URL ----------------
        shorteners = ['bit.ly', 'tinyurl', 't.co', 'goo.gl', 'ow.ly']
        is_short = 1 if any(s in url for s in shorteners) else 0

        # ---------------- HOMOGRAPH ATTACK ----------------
        try:
            decoded = idna.decode(domain.encode('utf-8'))
            homograph = 1 if decoded != domain else 0
        except:
            homograph = 1

        # ---------------- PATH FEATURES ----------------
        path = parsed.path
        path_length = len(path)
        path_depth = path.count('/')

        # ---------------- DOMAIN FEATURES ----------------
        digit_in_domain = sum(c.isdigit() for c in domain)
        alpha_in_domain = sum(c.isalpha() for c in domain)

        # ---------------- RATIO FEATURES ----------------
        digit_ratio = digit_in_domain / (len(domain)+1)
        special_ratio = sum(not c.isalnum() for c in url) / (len(url)+1)

        # ---------------- FINAL FEATURE VECTOR ----------------
        features = {
            "url_length": url_length,
            "domain_length": domain_length,
            "subdomain_length": subdomain_length,

            "count_dot": count_dot,
            "count_hyphen": count_hyphen,
            "count_at": count_at,
            "count_question": count_question,
            "count_percent": count_percent,
            "count_equal": count_equal,

            "count_http": count_http,
            "count_https": count_https,
            "count_www": count_www,

            "has_ip": has_ip,
            "has_https": has_https,
            "has_port": has_port,
            "has_at_symbol": has_at_symbol,

            "suspicious_words": suspicious_count,
            "risky_tld": risky_tld_flag,
            "is_short": is_short,
            "homograph": homograph,

            "path_length": path_length,
            "path_depth": path_depth,

            "digit_in_domain": digit_in_domain,
            "alpha_in_domain": alpha_in_domain,

            "digit_ratio": digit_ratio,
            "special_ratio": special_ratio
        }

        return features

    except:
        # fallback safe values
        return {key: 0 for key in [
            "url_length","domain_length","subdomain_length",
            "count_dot","count_hyphen","count_at","count_question",
            "count_percent","count_equal","count_http","count_https",
            "count_www","has_ip","has_https","has_port","has_at_symbol",
            "suspicious_words","risky_tld","is_short","homograph",
            "path_length","path_depth","digit_in_domain",
            "alpha_in_domain","digit_ratio","special_ratio"
        ]}