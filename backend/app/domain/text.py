"""Utilitários de texto usados pelas regras de negócio."""

import hashlib
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING = re.compile(r"^(utm_|fbclid|gclid|ref|trk|tracking)", re.I)


def normalize(text: str) -> str:
    """Minúsculas, espaços colapsados — para comparações tolerantes."""
    return re.sub(r"\s+", " ", text).strip().casefold()


def strip_accents(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", strip_accents(text)).strip("_")


def normalize_url(url: str) -> str:
    """Remove parâmetros de rastreamento e fragmentos, para detectar a mesma vaga com links diferentes."""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _TRACKING.match(k)]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(sorted(query)), ""))


def job_fingerprint(url: str | None, title: str, company: str | None, description: str) -> str:
    if url:
        basis = "url:" + normalize_url(url)
    else:
        basis = "txt:" + normalize(f"{title}|{company or ''}|{description[:2000]}")
    return hashlib.sha256(basis.encode()).hexdigest()


def term_pattern(term: str) -> re.Pattern[str]:
    """Casa o termo como palavra inteira. Hífen conta como parte da palavra,
    para "go" não casar com "go-live"."""
    return re.compile(rf"(?<![\w-]){re.escape(term.casefold())}(?![\w-])")


def find_spans(text: str, term: str) -> list[tuple[int, int]]:
    return [m.span() for m in term_pattern(term).finditer(text.casefold())]
