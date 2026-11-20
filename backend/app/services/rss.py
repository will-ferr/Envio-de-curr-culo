"""Leitura de feeds RSS/Atom de vagas."""

from dataclasses import dataclass

import feedparser
from bs4 import BeautifulSoup

from app.services.fetch import assert_public_url, fetch_html


@dataclass
class FeedEntry:
    title: str
    url: str
    description: str
    company: str


def read_feed(url: str, limit: int = 50) -> list[FeedEntry]:
    assert_public_url(url)
    feed = feedparser.parse(fetch_html(url))
    out = []
    for e in feed.entries[:limit]:
        link = e.get("link") or ""
        if not link:
            continue
        summary = BeautifulSoup(e.get("summary", "") or "", "html.parser").get_text("\n", strip=True)
        out.append(
            FeedEntry(
                title=(e.get("title") or "Vaga sem título").strip(),
                url=link,
                description=summary,
                company=(e.get("author") or "").strip(),
            )
        )
    return out
