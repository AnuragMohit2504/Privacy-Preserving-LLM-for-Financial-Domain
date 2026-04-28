"""
PII Extraction and Privacy Risk Scoring for LLM Interactions
Provides tools to measure and mitigate privacy risks in financial AI systems.
"""

import re
import json
import logging
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import Counter

import numpy as np

logger = logging.getLogger(__name__)


# Common PII patterns for financial documents
PII_PATTERNS = {
    # Financial identifiers
    "account_number": {
        "patterns": [
            r"\b\d{9,18}\b",  # Generic long numbers (account numbers)
            r"[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}(?:[A-Z0-9]?){0,16}",  # IBAN-like
        ],
        "risk_weight": 10.0,
        "category": "financial_id"
    },
    "credit_card": {
        "patterns": [
            r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12}|(?:2131|1800|35\d{3})\d{11})\b",
        ],
        "risk_weight": 10.0,
        "category": "financial_id"
    },
    "upi_id": {
        "patterns": [
            r"\b[A-Za-z0-9._-]+@[A-Za-z]+\b",  # UPI-like IDs
        ],
        "risk_weight": 8.0,
        "category": "financial_id"
    },
    "ifsc_code": {
        "patterns": [
            r"\b[A-Z]{4}0[A-Z0-9]{6}\b",  # IFSC code
        ],
        "risk_weight": 7.0,
        "category": "financial_id"
    },
    # Personal identifiers
    "email": {
        "patterns": [
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        ],
        "risk_weight": 6.0,
        "category": "personal_id"
    },
    "phone": {
        "patterns": [
            r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b",  # Indian mobile
            r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",  # Generic phone
        ],
        "risk_weight": 6.0,
        "category": "personal_id"
    },
    "pan_number": {
        "patterns": [
            r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",  # PAN card
        ],
        "risk_weight": 9.0,
        "category": "government_id"
    },
    "aadhaar": {
        "patterns": [
            r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",  # Aadhaar
        ],
        "risk_weight": 10.0,
        "category": "government_id"
    },
    "salary_amount": {
        "patterns": [
            r"Rs\.?\s*[\d,]+(?:\.\d{2})?",  # Rupee amounts
            r"₹\s*[\d,]+(?:\.\d{2})?",
            r"\b(?:salary|net pay|gross|ctc)[\s:]*(?:Rs\.?\s*)?[\d,]+(?:\.\d{2})?",
        ],
        "risk_weight": 4.0,
        "category": "financial_data"
    },
    "bank_name": {
        "patterns": [
            r"\b(?:SBI|HDFC|ICICI|Axis|PNB|BOB|Canara|Union Bank|Bank of India|Indian Bank|Yes Bank|Kotak|IndusInd|Federal Bank)\b",
        ],
        "risk_weight": 3.0,
        "category": "financial_data"
    },
    "date_of_birth": {
        "patterns": [
            r"\b(?:DOB|Date of Birth)[\s:]*\d{2}[/-]\d{2}[/-]\d{4}\b",
            r"\b\d{2}[/-]\d{2}[/-]\d{4}\b",  # Generic dates (may include DOB)
        ],
        "risk_weight": 5.0,
        "category": "personal_id"
    },
    "employee_id": {
        "patterns": [
            r"\b(?:EMP|Employee)[\s._-]*(?:ID|No|Number)[\s:]*[A-Z0-9]+\b",
        ],
        "risk_weight": 4.0,
        "category": "employment_id"
    },
}

# Financial keywords that increase sensitivity
SENSITIVE_KEYWORDS = {
    "high": [
        "password", "pin", "cvv", "otp", "secret", "confidential",
        "bank login", "net banking", "transaction password"
    ],
    "medium": [
        "loan", "emi", "investment", "portfolio", "insurance policy",
        "claim", "settlement", "dividend", "bonus", "esop"
    ],
    "low": [
        "account", "balance", "statement", "transaction", "transfer",
        "deposit", "withdrawal"
    ]
}


@dataclass
class PIIFinding:
    """Single PII finding."""
    pii_type: str
    value: str
    position: Tuple[int, int]
    risk_weight: float
    category: str


@dataclass
class PrivacyScore:
    """Privacy risk score for a query/response pair."""
    query_pii_count: int = 0
    query_pii_types: List[str] = None
    query_risk_score: float = 0.0  # 0-100
    query_risk_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    
    response_pii_count: int = 0
    response_pii_types: List[str] = None
    response_risk_score: float = 0.0
    response_risk_level: str = "LOW"
    
    overall_risk_score: float = 0.0
    overall_risk_level: str = "LOW"
    
    pii_findings: List[Dict] = None
    sanitization_actions: List[str] = None
    recommendations: List[str] = None
    
    timestamp: str = ""
    
    def __post_init__(self):
        if self.query_pii_types is None:
            self.query_pii_types = []
        if self.response_pii_types is None:
            self.response_pii_types = []
        if self.pii_findings is None:
            self.pii_findings = []
        if self.sanitization_actions is None:
            self.sanitization_actions = []
        if self.recommendations is None:
            self.recommendations = []
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


class PIIExtractor:
    """Extract PII from text using regex patterns."""
    
    def __init__(self, custom_patterns: Optional[Dict] = None):
        self.patterns = {**PII_PATTERNS, **(custom_patterns or {})}
        self.compiled_patterns = {}
        
        # Compile regex patterns
        for pii_type, config in self.patterns.items():
            self.compiled_patterns[pii_type] = [
                re.compile(p, re.IGNORECASE) for p in config["patterns"]
            ]
    
    def extract(self, text: str) -> List[PIIFinding]:
        """Extract all PII from text."""
        findings = []
        
        for pii_type, compiled_patterns in self.compiled_patterns.items():
            config = self.patterns[pii_type]
            
            for pattern in compiled_patterns:
                for match in pattern.finditer(text):
                    finding = PIIFinding(
                        pii_type=pii_type,
                        value=match.group(),
                        position=(match.start(), match.end()),
                        risk_weight=config["risk_weight"],
                        category=config["category"]
                    )
                    findings.append(finding)
        
        # Sort by position
        findings.sort(key=lambda x: x.position[0])
        
        # Remove overlaps (keep higher risk)
        findings = self._remove_overlaps(findings)
        
        return findings
    
    def _remove_overlaps(self, findings: List[PIIFinding]) -> List[PIIFinding]:
        """Remove overlapping findings, keeping higher risk ones."""
        if not findings:
            return findings
        
        filtered = [findings[0]]
        for finding in findings[1:]:
            last = filtered[-1]
            # Check overlap
            if finding.position[0] < last.position[1]:
                # Overlapping - keep higher risk
                if finding.risk_weight > last.risk_weight:
                    filtered[-1] = finding
            else:
                filtered.append(finding)
        
        return filtered
    
    def redact(self, text: str, findings: List[PIIFinding]) -> str:
        """Redact PII findings from text."""
        if not findings:
            return text
        
        # Sort in reverse position order to maintain indices
        sorted_findings = sorted(findings, key=lambda x: x.position[0], reverse=True)
        
        result = text
        for finding in sorted_findings:
            start, end = finding.position
            redaction = f"[{finding.pii_type.upper()}_REDACTED]"
            result = result[:start] + redaction + result[end:]
        
        return result


class PrivacyRiskScorer:
    """Score privacy risk of LLM interactions."""
    
    RISK_LEVELS = {
        "LOW": (0, 25),
        "MEDIUM": (25, 50),
        "HIGH": (50, 75),
        "CRITICAL": (75, 100)
    }
    
    def __init__(self):
        self.extractor = PIIExtractor()
    
    def score_interaction(
        self,
        query: str,
        response: str = "",
        user_context: Optional[Dict] = None
    ) -> PrivacyScore:
        """
        Score privacy risk of a query-response interaction.
        
        Args:
            query: User's query/prompt
            response: LLM's response
            user_context: Additional context (user role, data sensitivity, etc.)
        
        Returns:
            PrivacyScore with risk assessment
        """
        score = PrivacyScore(timestamp=datetime.utcnow().isoformat())
        
        # Extract PII from query
        query_findings = self.extractor.extract(query)
        score.query_pii_count = len(query_findings)
        score.query_pii_types = list(set(f.pii_type for f in query_findings))
        
        # Extract PII from response
        response_findings = self.extractor.extract(response)
        score.response_pii_count = len(response_findings)
        score.response_pii_types = list(set(f.pii_type for f in response_findings))
        
        # Calculate query risk
        query_risk = self._calculate_text_risk(query, query_findings)
        score.query_risk_score = query_risk["score"]
        score.query_risk_level = query_risk["level"]
        
        # Calculate response risk
        response_risk = self._calculate_text_risk(response, response_findings)
        score.response_risk_score = response_risk["score"]
        score.response_risk_level = response_risk["level"]
        
        # Overall risk (weighted: query matters more for privacy)
        score.overall_risk_score = min(100, score.query_risk_score * 0.7 + score.response_risk_score * 0.3)
        score.overall_risk_level = self._get_risk_level(score.overall_risk_score)
        
        # Record findings
        score.pii_findings = [
            {
                "type": f.pii_type,
                "value": f.value[:50] + "..." if len(f.value) > 50 else f.value,
                "category": f.category,
                "risk_weight": f.risk_weight,
                "source": "query" if f in query_findings else "response"
            }
            for f in query_findings + response_findings
        ]
        
        # Generate recommendations
        score.recommendations = self._generate_recommendations(score, query_findings)
        
        return score
    
    def _calculate_text_risk(self, text: str, findings: List[PIIFinding]) -> Dict[str, Any]:
        """Calculate risk score for a text."""
        if not text:
            return {"score": 0.0, "level": "LOW"}
        
        # Base score from PII
        base_score = sum(f.risk_weight for f in findings)
        
        # Category diversity bonus (more categories = higher risk)
        categories = set(f.category for f in findings)
        category_bonus = len(categories) * 5.0
        
        # Keyword sensitivity
        keyword_score = 0.0
        text_lower = text.lower()
        for level, keywords in SENSITIVE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    if level == "high":
                        keyword_score += 15.0
                    elif level == "medium":
                        keyword_score += 8.0
                    else:
                        keyword_score += 3.0
        
        # Length penalty (longer prompts leak more info)
        length_factor = min(1.0, len(text) / 1000) * 5.0
        
        # Normalize to 0-100
        raw_score = base_score + category_bonus + keyword_score + length_factor
        normalized_score = min(100.0, raw_score * 2.0)
        
        return {
            "score": round(normalized_score, 2),
            "level": self._get_risk_level(normalized_score)
        }
    
    def _get_risk_level(self, score: float) -> str:
        """Convert numeric score to risk level."""
        for level, (low, high) in self.RISK_LEVELS.items():
            if low <= score < high:
                return level
        return "CRITICAL" if score >= 75 else "LOW"
    
    def _generate_recommendations(
        self,
        score: PrivacyScore,
        findings: List[PIIFinding]
    ) -> List[str]:
        """Generate privacy recommendations."""
        recommendations = []
        
        if score.query_pii_count > 0:
            recommendations.append(
                f"Query contains {score.query_pii_count} PII items. "
                "Consider removing sensitive identifiers before sending to LLM."
            )
        
        if "account_number" in score.query_pii_types or "credit_card" in score.query_pii_types:
            recommendations.append(
                "CRITICAL: Financial account numbers detected. "
                "Never share account numbers with AI systems."
            )
        
        if "pan_number" in score.query_pii_types or "aadhaar" in score.query_pii_types:
            recommendations.append(
                "HIGH RISK: Government ID detected. "
                "Remove PAN/Aadhaar before submitting queries."
            )
        
        if score.response_pii_count > 0:
            recommendations.append(
                f"Response contains {score.response_pii_count} PII items. "
                "Review before sharing or storing."
            )
        
        if score.overall_risk_score > 50:
            recommendations.append(
                "Consider using differential privacy or data anonymization techniques."
            )
        
        if not recommendations:
            recommendations.append("No significant privacy risks detected.")
        
        return recommendations


class ResponseSanitizer:
    """Sanitize LLM responses to remove PII before display."""
    
    def __init__(self):
        self.extractor = PIIExtractor()
    
    def sanitize(self, response: str, aggressive: bool = False) -> Tuple[str, List[str]]:
        """
        Sanitize response by redacting PII.
        
        Args:
            response: Raw LLM response
            aggressive: If True, also redact salary amounts and financial data
        
        Returns:
            (sanitized_text, list_of_actions_taken)
        """
        findings = self.extractor.extract(response)
        actions = []
        
        if not findings:
            return response, ["No PII found - no sanitization needed"]
        
        # Filter findings based on aggressiveness
        if not aggressive:
            # Only redact high-risk PII
            high_risk_types = {"account_number", "credit_card", "pan_number", 
                             "aadhaar", "phone", "email", "upi_id", "ifsc_code"}
            findings = [f for f in findings if f.pii_type in high_risk_types]
        
        if not findings:
            return response, ["No high-risk PII found - minimal sanitization"]
        
        sanitized = self.extractor.redact(response, findings)
        
        # Record actions
        pii_type_counts = Counter(f.pii_type for f in findings)
        for pii_type, count in pii_type_counts.items():
            actions.append(f"Redacted {count} {pii_type}(s)")
        
        return sanitized, actions


class QueryDeduplicator:
    """Prevent repeated similar queries to reduce information leakage."""
    
    def __init__(self, similarity_threshold: float = 0.85, max_history: int = 100):
        self.similarity_threshold = similarity_threshold
        self.max_history = max_history
        self.query_history: List[str] = []
    
    def _jaccard_similarity(self, q1: str, q2: str) -> float:
        """Compute Jaccard similarity between two queries."""
        set1 = set(q1.lower().split())
        set2 = set(q2.lower().split())
        
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
    
    def is_similar_query(self, query: str) -> Tuple[bool, Optional[str]]:
        """
        Check if query is similar to a previous query.
        
        Returns:
            (is_similar, similar_query_from_history)
        """
        for past_query in self.query_history:
            similarity = self._jaccard_similarity(query, past_query)
            if similarity >= self.similarity_threshold:
                return True, past_query
        
        return False, None
    
    def add_query(self, query: str):
        """Add query to history."""
        self.query_history.append(query)
        if len(self.query_history) > self.max_history:
            self.query_history.pop(0)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get deduplicator statistics."""
        return {
            "queries_stored": len(self.query_history),
            "max_history": self.max_history,
            "similarity_threshold": self.similarity_threshold
        }


def demo_privacy_analysis():
    """Demonstrate privacy analysis on sample queries."""
    print("="*70)
    print("LLM PRIVACY ANALYSIS DEMO")
    print("="*70)
    
    scorer = PrivacyRiskScorer()
    sanitizer = ResponseSanitizer()
    
    test_queries = [
        # Low risk
        "What is the average savings rate for salaried employees?",
        
        # Medium risk
        "My salary is Rs. 75,000 per month. How much should I save?",
        
        # High risk
        "My account number 1234567890 has transactions from SBI. My PAN is ABCDE1234F.",
        
        # Critical risk
        "My credit card 4532123456789012 has CVV 123. My phone is 9876543210 and email is john@example.com",
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n--- Query {i} ---")
        print(f"Q: {query[:80]}...")
        
        score = scorer.score_interaction(query)
        
        print(f"Risk Score: {score.overall_risk_score}/100 ({score.overall_risk_level})")
        print(f"PII Found: {score.query_pii_count} items")
        print(f"PII Types: {', '.join(score.query_pii_types) if score.query_pii_types else 'None'}")
        
        if score.query_pii_count > 0:
            sanitized, actions = sanitizer.sanitize(query)
            print(f"Sanitized: {sanitized[:100]}...")
            print(f"Actions: {', '.join(actions)}")
        
        print(f"Recommendations:")
        for rec in score.recommendations[:2]:
            print(f"  - {rec}")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    demo_privacy_analysis()

