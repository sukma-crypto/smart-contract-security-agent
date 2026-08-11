"""Penyedia model bahasa.

Dua peran model dipisahkan sesuai Bagian 7.1: model konteks panjang untuk
menalar atas naskah utuh, dan model cepat untuk tugas bervolume tinggi dengan
tuntutan latensi rendah.

Bila tidak ada kunci API, Recens tidak berhenti. Seluruh fitur yang tidak
memerlukan penyusunan kalimat — perhitungan statistik, pemeriksaan naskah,
perenderan sitasi, perakitan format — tetap berjalan penuh, dan fitur penulisan
memakai jalur deterministik yang hasilnya lebih sederhana namun tetap benar.
"""

from __future__ import annotations

from ...config import get_settings
from .base import Completion, LLMUnavailable


class OfflineProvider:
    """Penanda bahwa penyusunan kalimat oleh model tidak tersedia."""

    name = "offline"
    available = False

    def complete(self, system, user, max_tokens=1024, temperature=0.3, fast=False) -> Completion:
        raise LLMUnavailable(
            "Model bahasa belum dikonfigurasi. Setel ANTHROPIC_API_KEY untuk mengaktifkan "
            "penyusunan kalimat; fitur lain tetap berjalan tanpa kunci API."
        )


class AnthropicProvider:
    """Penyedia berbasis Claude API."""

    name = "anthropic"
    available = True

    def __init__(self, api_key: str, long_context_model: str, fast_model: str):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise LLMUnavailable(
                "Paket 'anthropic' belum terpasang. Jalankan: pip install anthropic"
            ) from exc
        self._client = anthropic.Anthropic(api_key=api_key)
        self.long_context_model = long_context_model
        self.fast_model = fast_model

    def complete(self, system, user, max_tokens=1024, temperature=0.3, fast=False) -> Completion:
        model = self.fast_model if fast else self.long_context_model
        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # pragma: no cover - bergantung jaringan
            raise LLMUnavailable(f"Panggilan ke model gagal: {exc}") from exc

        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        usage = getattr(response, "usage", None)
        return Completion(
            text=text.strip(),
            model=model,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        )


_provider: object | None = None


def get_provider(force_reload: bool = False):
    global _provider
    if _provider is not None and not force_reload:
        return _provider

    settings = get_settings()
    if settings.has_llm:
        try:
            _provider = AnthropicProvider(
                api_key=settings.anthropic_api_key,
                long_context_model=settings.long_context_model,
                fast_model=settings.fast_model,
            )
        except LLMUnavailable:
            _provider = OfflineProvider()
    else:
        _provider = OfflineProvider()
    return _provider


def reset_provider() -> None:
    global _provider
    _provider = None
