"""Text utilities — cleaning, tokenization, lemmatization."""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")
_NON_PRINTABLE_RE = re.compile(r"[^\x20-\x7E\n\t]")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(r"[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}")
_URL_RE = re.compile(r"https?://[^\s]+|www\.[^\s]+", re.IGNORECASE)

# Lazy-loaded spaCy model
_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        import spacy
        try:
            _nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
        except OSError:
            # Model not downloaded — use blank English as fallback
            import spacy
            _nlp = spacy.blank("en")
    return _nlp


def clean_text(text: str) -> str:
    """Normalize whitespace, strip non-printable characters, normalize unicode."""
    text = unicodedata.normalize("NFKD", text)
    text = _NON_PRINTABLE_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def normalize_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def lemmatize(text: str) -> list[str]:
    """Return list of lowercased lemmas, excluding stopwords and punctuation."""
    nlp = _get_nlp()
    doc = nlp(text.lower())
    return [
        token.lemma_
        for token in doc
        if not token.is_stop and not token.is_punct and len(token.lemma_) > 1
    ]


def tokenize_words(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer."""
    return re.findall(r"\b[a-zA-Z0-9#+\-.]+\b", text.lower())


def split_sentences(text: str) -> list[str]:
    """Split text into sentences using simple heuristics."""
    # Use spaCy sentencizer if available, fallback to regex
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def split_bullet_points(text: str) -> list[str]:
    """Extract bullet points from text."""
    bullets = re.split(r"\n\s*[•\-\*\u2022\u2023\u25e6]\s*", text)
    return [b.strip() for b in bullets if b.strip() and len(b.strip()) > 10]


def extract_emails(text: str) -> list[str]:
    return _EMAIL_RE.findall(text)


def extract_phones(text: str) -> list[str]:
    return _PHONE_RE.findall(text)


def extract_urls(text: str) -> list[str]:
    return _URL_RE.findall(text)


def truncate_text(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, cutting at word boundary."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars].rsplit(" ", 1)[0]
    return truncated + "…"


def contains_numbers(text: str) -> bool:
    """Returns True if text contains any numerical quantity."""
    return bool(re.search(r"\d", text))


def has_quantified_impact(bullet: str) -> bool:
    """Check if a resume bullet has quantified metrics (%, $, numbers)."""
    patterns = [
        r"\d+%",           # percentages
        r"\$[\d,]+",       # dollar amounts
        r"\d+[kKmMbB]",   # 50K, 2M, etc.
        r"\d+\s*(times|x|\+)",  # 3x, 10+ times
        r"\b\d{2,}\b",    # any 2+ digit number
    ]
    return any(re.search(p, bullet) for p in patterns)
