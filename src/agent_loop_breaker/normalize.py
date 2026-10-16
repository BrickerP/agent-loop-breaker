"""Text normalization for goodbye / farewell repetition detection."""
from __future__ import annotations

import re
import unicodedata

# Farewell / closing politeness tokens that count as "same semantic loop".
_FAREWELL_RE = re.compile(
    r"\b("
    r"goodbye|good\s*bye|bye|bye[\s-]?bye|"
    r"see\s+you(?:\s+(?:soon|later|around|tomorrow))?|"
    r"take\s+care|farewell|cheers|"
    r"thanks?(?:\s+(?:again|so\s+much|a\s+lot))?|"
    r"thank\s+you(?:\s+(?:again|so\s+much|a\s+lot))?|"
    r"appreciate(?:\s+it)?|"
    r"have\s+a\s+(?:great|good|nice)\s+(?:day|one|evening|night)|"
    r"talk\s+(?:soon|later)|"
    r"looking\s+forward|"
    r"best(?:\s+regards)?|regards|"
    r"it(?:'s|\s+was)\s+(?:a\s+)?(?:pleasure|great)|"
    r"nice\s+(?:talking|chatting)|"
    r"all\s+the\s+best|"
    r"catch\s+you\s+later|"
    r"until\s+(?:next\s+time|then)|"
    r"so\s+long"
    r")\b",
    re.IGNORECASE,
)

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Lowercase, strip accents/punct, collapse whitespace."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower()
    t = _PUNCT_RE.sub(" ", t)
    t = _WS_RE.sub(" ", t).strip()
    return t


def is_farewell_like(text: str) -> bool:
    """True if the utterance is mostly farewell / closing politeness."""
    raw = text or ""
    if _FAREWELL_RE.search(raw):
        norm = normalize_text(raw)
        words = norm.split()
        if not words:
            return False
        # Count farewell-ish coverage: if ≥40% of tokens sit in farewell phrases, treat as loop fuel.
        # Also true if the whole short message is a farewell.
        if len(words) <= 8 and _FAREWELL_RE.search(raw):
            return True
        # Longer: check that farewell tokens dominate
        farewell_hits = list(_FAREWELL_RE.finditer(raw))
        covered = sum(len(m.group(0)) for m in farewell_hits)
        return covered / max(len(raw), 1) >= 0.35
    return False


def farewell_fingerprint(text: str) -> str:
    """Collapse farewell variants to a stable semantic bucket."""
    if is_farewell_like(text):
        return "FAREWELL"
    return normalize_text(text)
