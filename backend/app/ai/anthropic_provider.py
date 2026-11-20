"""Provedor Claude (API da Anthropic) com a chave da própria pessoa.

- Saída estruturada validada por Pydantic (`messages.parse` + `output_format`).
- PDF enviado direto como bloco `document` (sem extração de texto local).
- Fallback de recusa no servidor (`fallbacks: "default"`) nos modelos que o suportam.
- Validação de chave com `models.retrieve`, que não consome tokens.
"""

import base64

import anthropic

from app.ai.base import (
    AIAuthError,
    AIError,
    AIRateLimited,
    AIRefused,
    AIUnavailable,
    PDFInput,
    T,
    Usage,
)

DEFAULT_MODEL = "claude-opus-5-5"
MODEL_CHOICES = {
    "claude-opus-5-5": "Claude Opus 5.5 — melhor qualidade (padrão)",
    "claude-sonnet-5-5": "Claude Sonnet 5.5 — equilíbrio entre custo e qualidade",
    "claude-haiku-5-5": "Claude Haiku 5.5 — mais econômico",
}
EFFORT_CHOICES = ("low", "medium", "high")
# Modelos que aceitam o fallback de recusa no servidor (Haiku não tem).
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5", "claude-opus-5", "claude-fable-5-1", "claude-fable-5-2"}
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, effort: str = "medium", max_tokens: int = 16000):
        self.model = model or DEFAULT_MODEL
        self.effort = effort if effort in EFFORT_CHOICES else "medium"
        self.max_tokens = max_tokens
        self._client = anthropic.Anthropic(api_key=api_key, max_retries=2, timeout=180.0)

    def structured(
        self, *, system: str, prompt: str, schema: type[T], pdf: PDFInput | None = None, effort: str | None = None
    ) -> tuple[T, Usage]:
        content: list[dict] = []
        if pdf is not None:
            content.append(
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": base64.standard_b64encode(pdf.data).decode(),
                    },
                }
            )
        content.append({"type": "text", "text": prompt})

        extra: dict = {}
        if self.model in _FALLBACK_MODELS:
            extra = {"betas": [_FALLBACK_BETA], "fallbacks": "default"}

        try:
            response = self._client.beta.messages.parse(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": content}],
                output_format=schema,
                output_config={"effort": effort if effort in EFFORT_CHOICES else self.effort},
                **extra,
            )
        except anthropic.APIError as exc:
            raise translate_error(exc) from exc

        if response.stop_reason == "refusal":
            raise AIRefused("A IA recusou este pedido. Revise o texto da vaga ou do perfil e tente novamente.")
        if response.stop_reason == "max_tokens":
            raise AIError("A resposta da IA ficou incompleta (limite de tamanho). Tente com um texto menor.")
        parsed = response.parsed_output
        if parsed is None:
            raise AIError("A IA não devolveu dados no formato esperado.")
        usage = Usage(
            model=response.model, input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens
        )
        return parsed, usage

    def check(self) -> None:
        try:
            self._client.models.retrieve(self.model)
        except anthropic.APIError as exc:
            raise translate_error(exc) from exc


def translate_error(exc: anthropic.APIError) -> AIError:
    """Converte erros do SDK em mensagens úteis. Ordem: do mais específico para o mais geral."""
    if isinstance(exc, anthropic.AuthenticationError):
        return AIAuthError("Chave de API inválida ou revogada. Gere uma nova no Console da Anthropic.")
    if isinstance(exc, anthropic.PermissionDeniedError):
        return AIAuthError("Sua chave não tem permissão para usar este modelo.")
    if isinstance(exc, anthropic.NotFoundError):
        return AIError("Modelo não encontrado ou indisponível para a sua conta.")
    if isinstance(exc, anthropic.RateLimitError):
        return AIRateLimited("Limite de uso da sua conta atingido. Aguarde alguns minutos.")
    if isinstance(exc, anthropic.BadRequestError):
        return AIError(f"Pedido recusado pela API: {exc.message}")
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code >= 500:
            return AIUnavailable("O serviço de IA está instável no momento. Tentaremos novamente.")
        return AIError(f"Erro da API de IA ({exc.status_code}).")
    if isinstance(exc, anthropic.APIConnectionError):
        return AIUnavailable("Não foi possível conectar à API de IA. Verifique a internet.")
    return AIError("Erro inesperado ao chamar a IA.")
