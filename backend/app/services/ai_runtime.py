"""Obtém o provedor de IA configurado e registra o consumo de tokens."""

from sqlalchemy.orm import Session

from app.ai.base import AIProvider, Usage
from app.models import AiUsage
from app.services import settings

# Permite aos testes injetar um provedor falso.
_override: AIProvider | None = None


def set_override(provider: AIProvider | None) -> None:
    global _override
    _override = provider


def get_provider(db: Session) -> AIProvider | None:
    """Provedor configurado, ou None quando a pessoa não cadastrou chave (o sistema segue sem IA)."""
    if _override is not None:
        return _override
    key = settings.get(db, "ai.api_key")
    if not key:
        return None
    from app.ai.anthropic_provider import AnthropicProvider

    return AnthropicProvider(api_key=key, model=settings.get(db, "ai.model"), effort=settings.get(db, "ai.effort"))


def record_usage(db: Session, operation: str, usage: Usage) -> None:
    db.add(
        AiUsage(
            operation=operation, model=usage.model, input_tokens=usage.input_tokens, output_tokens=usage.output_tokens
        )
    )
