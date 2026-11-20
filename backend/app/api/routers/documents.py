"""Documentos gerados: edição, pré-visualização (HTML) e download (PDF)."""

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from app.api.deps import DB, CurrentOwner
from app.api.routers.jobs import doc_out
from app.errors import NotFound
from app.models import Document
from app.services import documents as docs_svc
from app.services import profile as profile_svc
from app.services import queue

router = APIRouter(prefix="/documents", tags=["documentos"])


def _get(db: DB, doc_id: int) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise NotFound("Documento não encontrado.")
    return doc


class DocumentIn(BaseModel):
    content: dict
    template: str | None = None


@router.get("/{doc_id}")
def get_document(doc_id: int, db: DB, _: CurrentOwner) -> dict:
    return doc_out(_get(db, doc_id))


@router.put("/{doc_id}")
def update_document(doc_id: int, body: DocumentIn, db: DB, _: CurrentOwner) -> dict:
    doc = docs_svc.update_content(db, _get(db, doc_id), body.content, body.template)
    task = queue.enqueue(db, "render_document", {"document_id": doc.id})
    db.commit()
    return {**doc_out(doc), "task_id": task.id}


@router.get("/{doc_id}/preview", response_class=HTMLResponse)
def preview(doc_id: int, db: DB, _: CurrentOwner) -> HTMLResponse:
    html = docs_svc.html_for(_get(db, doc_id), profile_svc.get_profile(db))
    # Exibido num iframe sandbox: sem scripts, sem recursos externos.
    return HTMLResponse(
        html,
        headers={
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'self'",
            "Cache-Control": "no-store",
        },
    )


@router.get("/{doc_id}/pdf")
def download(doc_id: int, db: DB, _: CurrentOwner) -> FileResponse:
    doc = _get(db, doc_id)
    path = docs_svc.ensure_pdf(db, doc)
    db.commit()
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=docs_svc.pdf_filename(doc, profile_svc.get_profile(db)),
        headers={"Cache-Control": "no-store"},
    )
