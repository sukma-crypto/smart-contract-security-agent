"""Penyedia model bahasa: DeepSeek, OpenAI, dan Anthropic berdampingan.

Ketiganya dipakai bersama supaya biaya mengikuti berat pekerjaan. Penjenjangan
tugasnya ada di ``catalog``; di sini hanya soal bagaimana masing-masing
dipanggil.

Bila tidak ada satu pun kunci API, Recens tidak berhenti. Seluruh fitur yang
tidak memerlukan penyusunan kalimat — perhitungan statistik, pemeriksaan
naskah, perenderan sitasi, perakitan format — tetap berjalan penuh, dan fitur
penulisan memakai jalur deterministik yang hasilnya lebih sederhana namun tetap
benar.
"""

from __future__ import annotations

from ...config import get_settings
from .base import Completion, LLMUnavailable


class OfflineProvider:
    """Penanda bahwa penyusunan kalimat oleh model tidak tersedia."""

    name = "offline"
    available = False

    def complete(self, system, user, model_id="", max_tokens=1024, temperature=0.3) -> Completion:
        raise LLMUnavailable(
            "Model bahasa belum dikonfigurasi. Setel salah satu dari DEEPSEEK_API_KEY, "
            "OPENAI_API_KEY, atau ANTHROPIC_API_KEY untuk mengaktifkan penyusunan "
            "kalimat; fitur lain tetap berjalan tanpa kunci API."
        )


class AnthropicProvider:
    """Penyedia berbasis Claude API."""

    name = "anthropic"
    available = True

    def __init__(self, api_key: str):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise LLMUnavailable(
                "Paket 'anthropic' belum terpasang. Jalankan: pip install anthropic"
            ) from exc
        self._client = anthropic.Anthropic(api_key=api_key)

    def complete(self, system, user, model_id="", max_tokens=1024, temperature=0.3) -> Completion:
        try:
            response = self._client.messages.create(
                model=model_id,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # pragma: no cover - bergantung jaringan
            raise LLMUnavailable(f"Panggilan ke {model_id} gagal: {exc}") from exc

        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        usage = getattr(response, "usage", None)
        return Completion(
            text=text.strip(),
            model=model_id,
            provider=self.name,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        )


class OpenAICompatibleProvider:
    """Penyedia yang berbicara protokol chat completions OpenAI.

    DeepSeek memakai protokol yang sama persis dengan OpenAI dan hanya berbeda
    alamat pangkalannya, jadi satu kelas melayani keduanya. Menyalin kelas ini
    menjadi dua hanya akan melipatgandakan tempat memperbaiki bug yang sama.
    """

    available = True

    def __init__(self, api_key: str, base_url: str | None, name: str):
        try:
            import openai
        except ImportError as exc:  # pragma: no cover
            raise LLMUnavailable(
                "Paket 'openai' belum terpasang. Jalankan: pip install openai"
            ) from exc
        self.name = name
        self._client = openai.OpenAI(
            api_key=api_key, **({"base_url": base_url} if base_url else {})
        )

    def complete(self, system, user, model_id="", max_tokens=1024, temperature=0.3) -> Completion:
        try:
            response = self._client.chat.completions.create(
                model=model_id,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as exc:  # pragma: no cover - bergantung jaringan
            raise LLMUnavailable(f"Panggilan ke {model_id} gagal: {exc}") from exc

        pilihan = response.choices[0] if response.choices else None
        text = (getattr(getattr(pilihan, "message", None), "content", "") or "").strip()
        usage = getattr(response, "usage", None)
        return Completion(
            text=text,
            model=model_id,
            provider=self.name,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )


_providers: dict[str, object] | None = None


def get_providers(force_reload: bool = False) -> dict[str, object]:
    """Penyedia yang benar-benar bisa dipakai, dipetakan menurut namanya.

    Yang kuncinya tidak disetel tidak muncul di sini sama sekali. Perute
    membaca peta ini untuk memutuskan cadangan, sehingga penyedia yang tidak
    terpasang dilewati tanpa perlu satu panggilan gagal lebih dulu — panggilan
    gagal pun ada ongkos latensinya, dan pada penyedia tertentu ada ongkos
    uangnya.
    """
    global _providers
    if _providers is not None and not force_reload:
        return _providers

    settings = get_settings()
    tersedia: dict[str, object] = {}

    if settings.deepseek_api_key:
        try:
            tersedia["deepseek"] = OpenAICompatibleProvider(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                name="deepseek",
            )
        except LLMUnavailable:
            pass
    if settings.openai_api_key:
        try:
            tersedia["openai"] = OpenAICompatibleProvider(
                api_key=settings.openai_api_key, base_url=None, name="openai"
            )
        except LLMUnavailable:
            pass
    if settings.anthropic_api_key:
        try:
            tersedia["anthropic"] = AnthropicProvider(api_key=settings.anthropic_api_key)
        except LLMUnavailable:
            pass

    _providers = tersedia
    return _providers


def get_provider(force_reload: bool = False):
    """Satu penyedia untuk pemeriksaan ketersediaan yang sederhana."""
    tersedia = get_providers(force_reload)
    if not tersedia:
        return OfflineProvider()
    return next(iter(tersedia.values()))


def reset_provider() -> None:
    global _providers
    _providers = None
