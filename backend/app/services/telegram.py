"""Cliente mínimo da Bot API do Telegram.

Usa long polling (getUpdates) em vez de webhook: a instância roda na casa da
pessoa, sem domínio nem IP público.
"""

import html
import json
from pathlib import Path

import httpx

from app.errors import ExternalError

API = "https://api.telegram.org"


class TelegramClient:
    def __init__(self, token: str, timeout: float = 35.0):
        self._base = f"{API}/bot{token}"
        self._http = httpx.Client(timeout=timeout)

    def _call(self, method: str, **kwargs) -> dict | list:
        try:
            resp = self._http.post(f"{self._base}/{method}", **kwargs)
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ExternalError("Não foi possível falar com o Telegram.", code="TELEGRAM_ERROR") from exc
        if not data.get("ok"):
            desc = data.get("description", "erro desconhecido")
            code = "TELEGRAM_AUTH" if resp.status_code == 401 else "TELEGRAM_ERROR"
            raise ExternalError(f"Telegram: {desc}", code=code)
        return data["result"]

    def get_me(self) -> dict:
        return self._call("getMe")  # type: ignore[return-value]

    def get_updates(self, offset: int | None, timeout: int = 25) -> list[dict]:
        payload = {"timeout": timeout, "allowed_updates": ["message", "callback_query"]}
        if offset is not None:
            payload["offset"] = offset
        return self._call("getUpdates", json=payload)  # type: ignore[return-value]

    def send_message(self, chat_id: str, text: str, buttons: list[list[tuple[str, str]]] | None = None) -> dict:
        payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
        if buttons:
            payload["reply_markup"] = _keyboard(buttons)
        return self._call("sendMessage", json=payload)  # type: ignore[return-value]

    def send_document(
        self, chat_id: str, path: Path, caption: str, buttons: list[list[tuple[str, str]]] | None = None
    ) -> dict:
        data: dict = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
        if buttons:
            data["reply_markup"] = json.dumps(_keyboard(buttons))
        with path.open("rb") as f:
            return self._call("sendDocument", data=data, files={"document": (path.name, f, "application/pdf")})  # type: ignore[return-value]

    def answer_callback(self, callback_id: str, text: str = "") -> None:
        self._call("answerCallbackQuery", json={"callback_query_id": callback_id, "text": text})

    def close(self) -> None:
        self._http.close()


def _keyboard(buttons: list[list[tuple[str, str]]]) -> dict:
    """Botões (texto, callback_data | url). Valores começando com http viram link."""
    rows = []
    for row in buttons:
        rows.append(
            [
                {"text": text, "url": value} if value.startswith("http") else {"text": text, "callback_data": value}
                for text, value in row
            ]
        )
    return {"inline_keyboard": rows}


def esc(text: str | None) -> str:
    """Escapa conteúdo dinâmico: um título de vaga com '&' ou '<' quebraria o parse_mode HTML."""
    return html.escape(text or "", quote=False)
