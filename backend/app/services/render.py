"""Renderização de documentos: Jinja2 → HTML → PDF (Chromium via Playwright)."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
RESUME_TEMPLATES = {
    "classico": "Clássico (uma coluna, máxima compatibilidade com ATS)",
    "moderno": "Moderno (cabeçalho em destaque)",
}

# autoescape: o conteúdo vem da IA e do usuário — nunca pode injetar HTML no documento.
_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape(["html"]))


def render_resume_html(template: str, context: dict) -> str:
    if template not in RESUME_TEMPLATES:
        template = "classico"
    return _env.get_template(f"resume/{template}.html").render(**context)


def render_letter_html(context: dict) -> str:
    return _env.get_template("cover_letter.html").render(**context)


def html_to_pdf(html: str, dest: Path) -> Path:
    """Gera o PDF sem acesso à rede: o documento é autocontido e nada externo deve ser carregado."""
    from playwright.sync_api import sync_playwright

    dest.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            context = browser.new_context(java_script_enabled=False, offline=True)
            page = context.new_page()
            page.set_content(html, wait_until="load")
            page.pdf(path=str(dest), format="A4", prefer_css_page_size=True, print_background=True)
        finally:
            browser.close()
    return dest
