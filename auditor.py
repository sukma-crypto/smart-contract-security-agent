"""
Smart Contract Security Auditor
Multi-agent pipeline for Solidity vulnerability detection.
"""

import json
import time
from dataclasses import dataclass, field
from typing import List, Optional
from agent.planner import PlannerAgent
from agent.executors import VulnerabilityDetector, LogicAuditor, InfoLeakageScanner
from agent.critic import CriticAgent
from agent.rag import SecurityKnowledgeBase
from agent.defenses import InputDefenseLayer, OutputDefenseLayer


@dataclass
class Vulnerability:
    type: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    line: Optional[int]
    description: str
    recommendation: str
    confidence: float

    def to_dict(self):
        return {
            "type": self.type,
            "severity": self.severity,
            "line": self.line,
            "description": self.description,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
        }


@dataclass
class AuditReport:
    contract_name: str
    risk_level: str
    vulnerabilities: List[Vulnerability] = field(default_factory=list)
    false_positive_filtered: int = 0
    audit_time_seconds: float = 0.0
    rag_references: List[str] = field(default_factory=list)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps({
            "contract": self.contract_name,
            "risk_level": self.risk_level,
            "vulnerabilities": [v.to_dict() for v in self.vulnerabilities],
            "false_positive_filtered": self.false_positive_filtered,
            "audit_time_seconds": self.audit_time_seconds,
            "rag_references": self.rag_references,
        }, indent=indent)

    def summary(self) -> str:
        counts = {}
        for v in self.vulnerabilities:
            counts[v.severity] = counts.get(v.severity, 0) + 1
        return (
            f"[{self.risk_level}] {self.contract_name}: "
            f"{len(self.vulnerabilities)} issues found — "
            + ", ".join(f"{k}: {v}" for k, v in counts.items())
        )


class SmartContractAuditor:
    """
    Orchestrates the multi-agent smart contract audit pipeline.

    Flow:
        1. InputDefenseLayer  — sanitize input, detect prompt injection
        2. PlannerAgent       — decompose audit into subtasks
        3. Executor Agents    — run parallel vulnerability detectors
        4. RAG Knowledge Base — enrich findings with CVE/OWASP context
        5. CriticAgent        — filter false positives, validate findings
        6. OutputDefenseLayer — ensure no sensitive data in final report
    """

    def __init__(self, model: str = "gpt-4o", verbose: bool = True):
        self.model = model
        self.verbose = verbose
        self.input_defense = InputDefenseLayer()
        self.output_defense = OutputDefenseLayer()
        self.planner = PlannerAgent(model=model)
        self.executors = [
            VulnerabilityDetector(model=model),
            LogicAuditor(model=model),
            InfoLeakageScanner(model=model),
        ]
        self.critic = CriticAgent(model=model)
        self.rag = SecurityKnowledgeBase()

    def audit(self, contract_code: str, contract_name: str = "Contract") -> AuditReport:
        start = time.time()

        if self.verbose:
            print(f"\n🔍 Starting audit: {contract_name}")

        # Step 1: Input defense — block prompt injection attempts
        safe_code = self.input_defense.sanitize(contract_code)
        if self.input_defense.is_malicious(safe_code):
            raise ValueError("⚠️ Potential prompt injection detected in contract input.")

        # Step 2: Planner decomposes the task
        tasks = self.planner.plan(safe_code)
        if self.verbose:
            print(f"  📋 Planner created {len(tasks)} audit tasks")

        # Step 3: Executors run their specialized analyses
        raw_findings: List[Vulnerability] = []
        for executor in self.executors:
            findings = executor.analyze(safe_code, tasks)
            raw_findings.extend(findings)
            if self.verbose:
                print(f"  ✅ {executor.__class__.__name__}: {len(findings)} findings")

        # Step 4: RAG enrichment — link findings to known CVEs
        rag_refs = self.rag.enrich(raw_findings)

        # Step 5: Critic filters false positives and scores confidence
        validated, filtered_count = self.critic.validate(raw_findings, safe_code)

        # Step 6: Output defense — ensure no sensitive data leaks
        validated = self.output_defense.filter(validated)

        # Determine overall risk level
        risk_level = self._calculate_risk(validated)

        elapsed = round(time.time() - start, 2)

        report = AuditReport(
            contract_name=contract_name,
            risk_level=risk_level,
            vulnerabilities=validated,
            false_positive_filtered=filtered_count,
            audit_time_seconds=elapsed,
            rag_references=rag_refs,
        )

        if self.verbose:
            print(f"\n📊 {report.summary()}")
            print(f"⏱️  Completed in {elapsed}s\n")

        return report

    def _calculate_risk(self, vulnerabilities: List[Vulnerability]) -> str:
        if not vulnerabilities:
            return "SAFE"
        severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}
        max_severity = max(v.severity for v in vulnerabilities, key=lambda s: severity_order.get(s, 0))
        return max_severity
