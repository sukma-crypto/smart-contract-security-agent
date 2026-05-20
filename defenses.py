"""
Input & Output Defense Layers
Protects the LLM pipeline from prompt injection, jailbreaks, and sensitive data leakage.
Aligned with OWASP Top 10 Risks for LLMs.
"""

import re
from typing import List
from agent.auditor import Vulnerability


# ─────────────────────────────────────────────────────────────────────────────
# OWASP LLM01: Prompt Injection Patterns
# ─────────────────────────────────────────────────────────────────────────────
INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|above)\s+instructions",
    r"you\s+are\s+now\s+a",
    r"forget\s+your\s+instructions",
    r"act\s+as\s+(if\s+you\s+are|a)",
    r"disregard\s+your",
    r"new\s+system\s+prompt",
    r"jailbreak",
    r"dan\s+mode",
    r"do\s+anything\s+now",
    r"override\s+(system|safety|security)",
    r"\\n\\nHuman:",          # Multi-turn injection attempts
    r"<\|im_start\|>",        # Tokenizer injection
    r"\[INST\]",               # Instruction injection
]

# ─────────────────────────────────────────────────────────────────────────────
# OWASP LLM06: Sensitive Information Disclosure patterns
# ─────────────────────────────────────────────────────────────────────────────
SENSITIVE_PATTERNS = [
    r"private\s+key\s*[:=]\s*0x[0-9a-fA-F]{64}",  # Ethereum private keys
    r"sk-[a-zA-Z0-9]{48}",                           # OpenAI API keys
    r"password\s*[:=]\s*\S+",
    r"secret\s*[:=]\s*\S+",
    r"api[_-]?key\s*[:=]\s*\S+",
    r"AWS_SECRET_ACCESS_KEY",
    r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",    # PEM private keys
]


class InputDefenseLayer:
    """
    OWASP LLM01 — Prompt Injection Defense
    Sanitizes user-provided contract code before passing to LLM agents.
    """

    def sanitize(self, code: str) -> str:
        """Remove or escape potentially injected content."""
        # Normalize line endings
        code = code.replace("\r\n", "\n").replace("\r", "\n")
        # Strip null bytes and control characters (except newlines/tabs)
        code = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", code)
        return code

    def is_malicious(self, code: str) -> bool:
        """
        Detect prompt injection attempts embedded in contract code.
        Returns True if injection is suspected.
        """
        code_lower = code.lower()
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, code_lower, re.IGNORECASE):
                return True
        return False

    def extract_comments(self, code: str) -> List[str]:
        """Extract all Solidity comments for separate injection scanning."""
        single = re.findall(r"//.*$", code, re.MULTILINE)
        multi = re.findall(r"/\*[\s\S]*?\*/", code)
        return single + multi

    def scan_comments_for_injection(self, code: str) -> bool:
        """Comments are a common injection vector — scan them separately."""
        comments = self.extract_comments(code)
        for comment in comments:
            if self.is_malicious(comment):
                return True
        return False


class OutputDefenseLayer:
    """
    OWASP LLM06 — Sensitive Information Leakage Defense
    Ensures the audit report does not accidentally expose secrets.
    """

    def filter(self, vulnerabilities: List[Vulnerability]) -> List[Vulnerability]:
        """Redact any sensitive data that leaked into vulnerability descriptions."""
        cleaned = []
        for v in vulnerabilities:
            v.description = self._redact(v.description)
            v.recommendation = self._redact(v.recommendation)
            cleaned.append(v)
        return cleaned

    def _redact(self, text: str) -> str:
        """Replace sensitive patterns with [REDACTED]."""
        for pattern in SENSITIVE_PATTERNS:
            text = re.sub(pattern, "[REDACTED]", text, flags=re.IGNORECASE)
        return text

    def scan_for_leakage(self, text: str) -> bool:
        """Returns True if sensitive data is detected in output."""
        for pattern in SENSITIVE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False


class JailbreakDetector:
    """
    OWASP LLM02 — Insecure Output Handling / Jailbreak Detection
    Monitors LLM responses for signs of successful jailbreak.
    """

    JAILBREAK_RESPONSE_INDICATORS = [
        "i am now",
        "as an ai without restrictions",
        "i have been freed",
        "dan mode enabled",
        "i will do anything",
        "safety guidelines don't apply",
    ]

    def is_jailbroken_response(self, response: str) -> bool:
        response_lower = response.lower()
        for indicator in self.JAILBREAK_RESPONSE_INDICATORS:
            if indicator in response_lower:
                return True
        return False
