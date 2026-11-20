"""Interface de provedor de IA.

O resto do sistema depende só desta interface; trocar de provedor ou usar um
fake nos testes não exige mudar serviços nem rotas.
"""

from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class AIError(Exception):
    """Falha da IA com mensagem segura para mostrar ao usuário."""

    code = "AI_ERROR"
    retryable = False

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class AINotConfigured(AIError):
    code = "AI_NOT_CONFIGURED"


class AIAuthError(AIError):
    code = "AI_AUTH"


class AIRateLimited(AIError):
    code = "AI_RATE_LIMITED"
    retryable = True


class AIUnavailable(AIError):
    code = "AI_UNAVAILABLE"
    retryable = True


class AIRefused(AIError):
    code = "AI_REFUSED"


@dataclass
class Usage:
    model: str
    input_tokens: int
    output_tokens: int


@dataclass
class PDFInput:
    data: bytes


class AIProvider(Protocol):
    model: str

    def structured(
        self, *, system: str, prompt: str, schema: type[T], pdf: PDFInput | None = None, effort: str | None = None
    ) -> tuple[T, Usage]:
        """Executa uma chamada e devolve a saída validada contra `schema`."""
        ...

    def check(self) -> None:
        """Valida a credencial sem gastar tokens. Levanta AIError se inválida."""
        ...
