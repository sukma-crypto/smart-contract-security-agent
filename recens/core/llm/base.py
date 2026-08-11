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
    input_tokens: int = 0
    output_tokens: int = 0

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
        max_tokens: int = 1024,
        temperature: float = 0.3,
        fast: bool = False,
    ) -> Completion: ...
