"""Busca e extração do texto de páginas de vaga.

Proteções: só http/https, bloqueio de endereços internos (evita usar a instância
para acessar a rede local), tamanho máximo e timeout.
"""

import ipaddress
import json
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from app.errors import BusinessRule, ExternalError

MAX_BYTES = 3 * 1024 * 1024
USER_AGENT = "Mozilla/5.0 (compatible; Candidaturas/0.1; +https://github.com/will-ferr/Envio-de-curr-culo)"


@dataclass
class FetchedJob:
    url: str
    title: str
    company: str
    location: str
    description: str


def assert_public_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise BusinessRule("Informe um link http(s) válido.", code="INVALID_URL")
    try:
        infos = socket.getaddrinfo(parts.hostname, None)
    except socket.gaierror as exc:
        raise BusinessRule("Não foi possível encontrar o endereço do link.", code="INVALID_URL") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise BusinessRule("Links para endereços internos não são permitidos.", code="INVALID_URL")


def fetch_html(url: str, timeout: float = 15.0, max_redirects: int = 5) -> str:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False, headers={"User-Agent": USER_AGENT}) as client:
            for _ in range(max_redirects + 1):
                # Cada salto é validado ANTES da requisição: um redirect não pode levar à rede interna.
                assert_public_url(url)
                with client.stream("GET", url) as resp:
                    if resp.is_redirect:
                        url = str(resp.next_request.url) if resp.next_request else url
                        continue
                    resp.raise_for_status()
                    chunks, size = [], 0
                    for chunk in resp.iter_bytes():
                        size += len(chunk)
                        if size > MAX_BYTES:
                            raise BusinessRule("A página é grande demais para ser lida.", code="PAGE_TOO_LARGE")
                        chunks.append(chunk)
                    return b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")
            raise ExternalError("O link redireciona vezes demais.")
    except httpx.HTTPStatusError as exc:
        raise ExternalError(f"O site respondeu com erro {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        raise ExternalError("Não foi possível acessar o link da vaga.") from exc


def _text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text("\n", strip=True)


def _job_posting(soup: BeautifulSoup) -> dict | None:
    """Muitos sites de vaga publicam schema.org/JobPosting em JSON-LD — dado estruturado e confiável."""
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for item in items:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return None


def parse_job_page(url: str, html: str) -> FetchedJob:
    soup = BeautifulSoup(html, "html.parser")
    posting = _job_posting(soup)
    if posting:
        org = posting.get("hiringOrganization") or {}
        loc = posting.get("jobLocation") or {}
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        address = (loc.get("address") or {}) if isinstance(loc, dict) else {}
        location = ", ".join(
            x for x in [address.get("addressLocality"), address.get("addressRegion")] if isinstance(x, str) and x
        )
        return FetchedJob(
            url=url,
            title=str(posting.get("title") or "").strip() or "Vaga sem título",
            company=str(org.get("name") or "") if isinstance(org, dict) else "",
            location=location,
            description=_text(str(posting.get("description") or "")) or _main_text(soup),
        )

    title = (soup.title.string if soup.title and soup.title.string else "").strip()
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = str(og["content"]).strip()
    return FetchedJob(url=url, title=title or "Vaga sem título", company="", location="", description=_main_text(soup))


def _main_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "svg", "form"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    lines = [ln for ln in main.get_text("\n", strip=True).splitlines() if len(ln) > 1]
    return "\n".join(lines)[:20000]


def fetch_job(url: str) -> FetchedJob:
    return parse_job_page(url, fetch_html(url))
