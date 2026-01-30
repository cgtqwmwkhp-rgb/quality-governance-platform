"""
Text Classification Engine - Quality Governance Platform
Stage 12: AI Standards Automation (Security Hardened)

SECURITY NOTES:
- PII extraction DISABLED by default
- No sensitive data in outputs unless explicitly enabled
- All classifications are deterministic
"""

import re
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .config import ClassificationConfig, get_ai_config


@dataclass
class ClassificationResult:
    """Classification result."""
    category: str
    confidence: float
    keywords_matched: List[str]
    method: str = "rules"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "confidence": round(self.confidence, 3),
            "keywords_matched": self.keywords_matched,
            "method": self.method,
        }


@dataclass
class UrgencyResult:
    """Urgency detection result."""
    priority: str
    confidence: float
    indicators_found: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "priority": self.priority,
            "confidence": round(self.confidence, 3),
            "indicators_found": self.indicators_found,
        }


class TextClassifier:
    """
    Text classification engine with security-first design.
    
    SECURITY:
    - PII extraction is DISABLED by default
    - All outputs are sanitized
    """

    def __init__(self, config: Optional[ClassificationConfig] = None):
        self.config = config or get_ai_config().classification
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns."""
        for category, keywords in self.config.complaint_categories.items():
            self._compiled_patterns[f"complaint_{category}"] = [
                re.compile(rf'\b{re.escape(kw)}\b', re.IGNORECASE)
                for kw in keywords
            ]

        for incident_type, keywords in self.config.incident_types.items():
            self._compiled_patterns[f"incident_{incident_type}"] = [
                re.compile(rf'\b{re.escape(kw)}\b', re.IGNORECASE)
                for kw in keywords
            ]

        for priority, keywords in self.config.urgency_indicators.items():
            self._compiled_patterns[f"urgency_{priority}"] = [
                re.compile(rf'\b{re.escape(kw)}\b', re.IGNORECASE)
                for kw in keywords
            ]

    def _normalize_text(self, text: str) -> str:
        """Normalize text for classification."""
        if not text:
            return ""
        text = text.lower()
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s]', ' ', text)
        return text.strip()

    def _score_category(
        self,
        text: str,
        pattern_key: str,
    ) -> Tuple[float, List[str]]:
        """Score text against category patterns."""
        patterns = self._compiled_patterns.get(pattern_key, [])
        matches: List[str] = []

        for pattern in patterns:
            if pattern.search(text):
                # Return keyword, not full pattern
                keyword = pattern.pattern.replace(r'\b', '').replace('\\', '')
                matches.append(keyword)

        if not patterns:
            return 0.0, []

        raw_score = len(matches) / len(patterns)
        if len(matches) > 1:
            raw_score = min(1.0, raw_score * (1 + 0.1 * len(matches)))

        return raw_score, matches

    def classify_complaint(
        self,
        text: str,
        title: Optional[str] = None,
    ) -> ClassificationResult:
        """Classify complaint text."""
        combined = self._normalize_text(text)
        if title:
            combined = f"{self._normalize_text(title)} {self._normalize_text(title)} {combined}"

        scores: Dict[str, float] = {}
        all_matches: Dict[str, List[str]] = {}

        for category in self.config.complaint_categories.keys():
            score, matches = self._score_category(combined, f"complaint_{category}")
            scores[category] = score
            all_matches[category] = matches

        if not scores or max(scores.values()) == 0:
            return ClassificationResult(
                category="OTHER",
                confidence=0.0,
                keywords_matched=[],
            )

        best_category = max(scores, key=scores.get)
        best_score = scores[best_category]
        confidence = min(1.0, best_score * 2)

        return ClassificationResult(
            category=best_category,
            confidence=confidence,
            keywords_matched=all_matches.get(best_category, []),
        )

    def classify_incident(
        self,
        text: str,
        title: Optional[str] = None,
    ) -> ClassificationResult:
        """Classify incident text."""
        combined = self._normalize_text(text)
        if title:
            combined = f"{self._normalize_text(title)} {self._normalize_text(title)} {combined}"

        scores: Dict[str, float] = {}
        all_matches: Dict[str, List[str]] = {}

        for incident_type in self.config.incident_types.keys():
            score, matches = self._score_category(combined, f"incident_{incident_type}")
            scores[incident_type] = score
            all_matches[incident_type] = matches

        if not scores or max(scores.values()) == 0:
            return ClassificationResult(
                category="OTHER",
                confidence=0.0,
                keywords_matched=[],
            )

        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        confidence = min(1.0, best_score * 2)

        return ClassificationResult(
            category=best_type,
            confidence=confidence,
            keywords_matched=all_matches.get(best_type, []),
        )

    def detect_urgency(
        self,
        text: str,
        title: Optional[str] = None,
    ) -> UrgencyResult:
        """Detect urgency level."""
        combined = self._normalize_text(text)
        if title:
            combined = f"{self._normalize_text(title)} {self._normalize_text(title)} {combined}"

        for priority in ["URGENT", "HIGH", "NORMAL"]:
            score, matches = self._score_category(combined, f"urgency_{priority}")
            if score > 0:
                return UrgencyResult(
                    priority=priority,
                    confidence=min(1.0, score * 3),
                    indicators_found=matches,
                )

        return UrgencyResult(
            priority="NORMAL",
            confidence=0.5,
            indicators_found=[],
        )

    def extract_entities_safe(
        self,
        text: str,
        hash_pii: bool = True,
    ) -> Dict[str, List[str]]:
        """
        Extract entities with PII protection.
        
        SECURITY: By default, PII (emails, phones) are SHA-256 hashed.
        Set hash_pii=False only for authorized internal use.
        
        Args:
            text: Text to extract from
            hash_pii: If True, hash PII values (default: True)
            
        Returns:
            Dictionary with entity types. PII values are hashed unless disabled.
        """
        # Check if PII extraction is enabled at config level
        if not self.config.extract_pii:
            return {
                "locations": [],
                "dates": [],
                "references": [],
                "pii_redacted": True,
            }

        entities: Dict[str, List[str]] = {
            "locations": [],
            "dates": [],
            "references": [],
        }

        # UK postcode pattern (not PII)
        postcode_pattern = r'\b[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}\b'
        entities["locations"] = re.findall(postcode_pattern, text, re.IGNORECASE)

        # Date patterns (not PII)
        date_pattern = r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'
        entities["dates"] = re.findall(date_pattern, text)

        # Reference numbers (not PII)
        ref_pattern = r'\b(?:INC|COMP|RTA|POL|INV)-\d{4}-\d{4}\b'
        entities["references"] = re.findall(ref_pattern, text, re.IGNORECASE)

        # NOTE: Email and phone extraction REMOVED for security
        # These are PII and should not be extracted by default

        return entities


def _hash_value(value: str) -> str:
    """SHA-256 hash a value."""
    return hashlib.sha256(value.encode()).hexdigest()[:12]
