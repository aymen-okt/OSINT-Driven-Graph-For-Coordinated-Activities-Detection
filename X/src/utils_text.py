import hashlib
import re
from urllib.parse import urlparse
from typing import List, Tuple


URL_RE = re.compile(r"(https?://[^\s)]+)", re.IGNORECASE)
HASHTAG_RE = re.compile(r"(#[A-Za-z0-9_]+)")


def hash_id(s: str, salt: str = "yt-osint") -> str:
    """Anonymize IDs (stable hash)."""
    h = hashlib.sha256((salt + "|" + s).encode("utf-8")).hexdigest()
    return h[:16]


def extract_urls(text: str) -> List[str]:
    if not text:
        return []
    urls = URL_RE.findall(text)
    # clean trailing punctuation
    clean = [u.rstrip(".,;:!?)\"'") for u in urls]
    return list(dict.fromkeys(clean))


def extract_domains(urls: List[str]) -> List[str]:
    out = []
    for u in urls:
        try:
            p = urlparse(u)
            if p.netloc:
                out.append(p.netloc.lower())
        except Exception:
            continue
    return list(dict.fromkeys(out))


def extract_hashtags(text: str) -> List[str]:
    if not text:
        return []
    tags = HASHTAG_RE.findall(text)
    # normalize lower
    tags = [t.lower() for t in tags]
    return list(dict.fromkeys(tags))


def normalize_text_basic(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"\s+", " ", t)
    return t


def sensational_score(text: str) -> float:
    """
    Very simple credibility heuristic (baseline), NOT a truth detector.
    Higher = more "sensational" style.
    """
    if not text:
        return 0.0
    t = text
    upper_ratio = sum(1 for c in t if c.isalpha() and c.isupper()) / max(1, sum(1 for c in t if c.isalpha()))
    excls = t.count("!")
    qmarks = t.count("?")
    caps_words = len(re.findall(r"\b[A-Z]{4,}\b", t))
    clickbait = len(re.findall(r"\b(shocking|bombshell|you won'?t believe|exposed|truth|lies|fraud)\b", t.lower()))
    return float(2.0 * upper_ratio + 0.2 * excls + 0.2 * qmarks + 0.3 * caps_words + 0.5 * clickbait)
