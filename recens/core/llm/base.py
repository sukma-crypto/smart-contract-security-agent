"""Antarmuka penyedia model bahasa."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class LLMUnavailable(RuntimeError):
    """Model bahasa tidak tersedia; pemanggil harus memakai jalur deterministik."""


@dataclass
class Completion:
    text: str
    model: str
    provider: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    #: Biaya panggilan ini dalam mikro-dolar, diisi perute setelah menghitung.
    cost_micros: int = 0
    #: Benar bila masukannya dipotong agar muat anggaran token.
    truncated: bool = False
    #: Benar bila hasil ini datang dari jenjang yang dinaikkan karena yang
    #: murah tidak lolos lantai mutu.
    escalated: bool = False

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@runtime_checkable
class Provider(Protocol):
    name: str
    available: bool

    def complete(
        self,
        system: str,
        user: str,
        model_id: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> Completion: ...
