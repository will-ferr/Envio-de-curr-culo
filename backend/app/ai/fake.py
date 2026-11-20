"""Provedor falso e determinístico para testes e para demonstração sem chave."""

from collections.abc import Callable

from pydantic import BaseModel

from app.ai.base import AIError, PDFInput, T, Usage


class FakeProvider:
    model = "fake"

    def __init__(
        self, responses: dict[type[BaseModel], BaseModel | Callable[[str], BaseModel] | AIError] | None = None
    ):
        self.responses = responses or {}
        self.calls: list[dict] = []

    def structured(
        self, *, system: str, prompt: str, schema: type[T], pdf: PDFInput | None = None, effort: str | None = None
    ) -> tuple[T, Usage]:
        self.calls.append({"system": system, "prompt": prompt, "schema": schema, "pdf": pdf is not None})
        resp = self.responses.get(schema)
        if isinstance(resp, AIError):
            raise resp
        if resp is None:
            raise AIError(f"FakeProvider sem resposta para {schema.__name__}")
        value = resp(prompt) if callable(resp) and not isinstance(resp, BaseModel) else resp
        return value, Usage(model=self.model, input_tokens=len(prompt) // 4, output_tokens=100)  # type: ignore[return-value]

    def check(self) -> None:
        return None
