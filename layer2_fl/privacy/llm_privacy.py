"""
LLM Privacy Measurement & Improvement Module
Since Ollama/llama3.2 doesn't provide actual privacy budgets,
this module implements proxy metrics to measure and improve privacy.
"""

import os
import re
import json
import logging
import hashlib
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import defaultdict

import numpy as np

# Import privacy metrics
from .privacy_metrics import (
    PrivacyRiskScorer, ResponseSanitizer, QueryDeduplicator,
    PIIExtractor, PrivacyScore
)

logger = logging.getLogger(__name__)


@dataclass
class LLMPrivacyAudit:
    """Audit record for LLM interaction privacy."""
    session_id: str
    user_email: str
    query: str
    response: str
    
    # Privacy scores
    query_pii_score: float = 0.0
    response_pii_score: float = 0.0
    overall_risk_score: float = 0.0
    risk_level: str = "LOW"
    
    # Proxy privacy budget
    information_leakage_score: float = 0.0  # Estimated info leaked
    query_diversity_score: float = 0.0  # How unique is this query
    repetition_penalty: float = 0.0  # Penalty for repeated queries
    
    # Synthetic privacy budget
    synthetic_epsilon_estimate: float = 0.0
    cumulative_epsilon: float = 0.0
    
    # Mitigations applied
    sanitization_actions: List[str] = None
    query_modified: bool = False
    response_modified: bool = False
    
    # Timestamps
    timestamp: str = ""
    processing_time_ms: float = 0.0
    
    def __post_init__(self):
        if self.sanitization_actions is None:
            self.sanitization_actions = []
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LLMPrivacyAuditor:
    """
    Main auditor for LLM privacy.
    
    Since we don't have access to the LLM's internal privacy budget,
    we implement proxy measurements:
    
    1. Information Leakage Proxy:
       - PII density in prompts
       - Semantic uniqueness of queries
       - Cumulative data exposure
    
    2. Membership Inference Simulation:
       - Check if responses contain exact input phrases
       - Detect potential memorization
    
    3. Synthetic Privacy Budget:
       - Query rate limiting
       - Output perturbation
       - Context window tracking
    
    4. Query Pattern Analysis:
       - Detect systematic data extraction attempts
       - Flag high-frequency similar queries
    """
    
    # Privacy budget parameters (synthetic)
    DEFAULT_EPSILON_BUDGET = 10.0  # Total privacy budget per user per day
    QUERY_EPSILON_COST = 0.1  # Base cost per query
    PII_EPSILON_MULTIPLIER = 2.0  # Multiplier for PII-containing queries
    REPETITION_EPSILON_MULTIPLIER = 1.5  # Multiplier for repeated queries
    
    def __init__(
        self,
        epsilon_budget: float = DEFAULT_EPSILON_BUDGET,
        enable_deduplication: bool = True,
        enable_sanitization: bool = True,
        enable_memorization_check: bool = True
    ):
        self.epsilon_budget = epsilon_budget
        self.enable_deduplication = enable_deduplication
        self.enable_sanitization = enable_sanitization
        self.enable_memorization_check = enable_memorization_check
        
        # Components
        self.risk_scorer = PrivacyRiskScorer()
        self.sanitizer = ResponseSanitizer()
        self.pii_extractor = PIIExtractor()
        self.deduplicator = QueryDeduplicator()
        
        # User privacy state tracking
        self.user_privacy_state: Dict[str, Dict] = defaultdict(lambda: {
            "cumulative_epsilon": 0.0,
            "query_count": 0,
            "total_pii_exposed": 0,
            "last_query_time": 0.0,
            "query_hashes": set()
        })
        
        # Audit log
        self.audit_log: List[LLMPrivacyAudit] = []
        
        logger.info(f"LLMPrivacyAuditor initialized: epsilon_budget={epsilon_budget}")
    
    def audit_interaction(
        self,
        user_email: str,
        query: str,
        response: str,
        session_id: str = ""
    ) -> Tuple[PrivacyScore, LLMPrivacyAudit]:
        """
        Audit a complete LLM interaction for privacy risks.
        
        Returns:
            (privacy_score, audit_record)
        """
        start_time = time.time()
        
        # Get user state
        user_state = self.user_privacy_state[user_email]
        
        # 1. Score privacy risk
        privacy_score = self.risk_scorer.score_interaction(query, response)
        
        # 2. Check for memorization
        memorization_risk = 0.0
        if self.enable_memorization_check:
            memorization_risk = self._check_memorization(query, response)
        
        # 3. Check query deduplication
        is_repeated = False
        if self.enable_deduplication:
            is_repeated, _ = self.deduplicator.is_similar_query(query)
            self.deduplicator.add_query(query)
        
        # 4. Calculate synthetic epsilon
        synthetic_epsilon = self._calculate_synthetic_epsilon(
            privacy_score, is_repeated, user_state
        )
        
        # 5. Update cumulative budget
        user_state["cumulative_epsilon"] += synthetic_epsilon
        user_state["query_count"] += 1
        user_state["total_pii_exposed"] += privacy_score.query_pii_count
        user_state["last_query_time"] = time.time()
        
        # 6. Sanitize response if needed
        sanitized_response = response
        sanitization_actions = []
        response_modified = False
        
        if self.enable_sanitization and privacy_score.response_pii_count > 0:
            aggressive = privacy_score.overall_risk_score > 50
            sanitized_response, sanitization_actions = self.sanitizer.sanitize(
                response, aggressive=aggressive
            )
            response_modified = sanitized_response != response
        
        # 7. Calculate information leakage proxy
        info_leakage = self._calculate_information_leakage(
            query, response, privacy_score, memorization_risk
        )
        
        # 8. Query diversity score
        query_hash = hashlib.md5(query.lower().encode()).hexdigest()[:16]
        is_new_query = query_hash not in user_state["query_hashes"]
        user_state["query_hashes"].add(query_hash)
        
        diversity_score = 1.0 if is_new_query else 0.3
        repetition_penalty = 0.5 if is_repeated else 0.0
        
        # Create audit record
        audit = LLMPrivacyAudit(
            session_id=session_id or f"{user_email}_{int(time.time())}",
            user_email=user_email,
            query=query[:500],  # Truncate for storage
            response=sanitized_response[:500],
            query_pii_score=privacy_score.query_risk_score,
            response_pii_score=privacy_score.response_risk_score,
            overall_risk_score=privacy_score.overall_risk_score,
            risk_level=privacy_score.overall_risk_level,
            information_leakage_score=info_leakage,
            query_diversity_score=diversity_score,
            repetition_penalty=repetition_penalty,
            synthetic_epsilon_estimate=synthetic_epsilon,
            cumulative_epsilon=user_state["cumulative_epsilon"],
            sanitization_actions=sanitization_actions,
            query_modified=False,  # We don't modify queries, just warn
            response_modified=response_modified,
            timestamp=datetime.utcnow().isoformat(),
            processing_time_ms=(time.time() - start_time) * 1000
        )
        
        self.audit_log.append(audit)
        
        # Log warning if budget exceeded
        if user_state["cumulative_epsilon"] > self.epsilon_budget:
            logger.warning(
                f"Privacy budget exceeded for {user_email}: "
                f"{user_state['cumulative_epsilon']:.2f} / {self.epsilon_budget}"
            )
        
        return privacy_score, audit
    
    def _check_memorization(self, query: str, response: str) -> float:
        """
        Check if the LLM response contains memorized content from the query.
        
        Returns:
            Memorization risk score (0-1)
        """
        # Extract phrases from query (3+ word sequences)
        query_words = query.lower().split()
        if len(query_words) < 3:
            return 0.0
        
        # Generate n-grams
        ngrams = []
        for n in range(3, min(6, len(query_words) + 1)):
            for i in range(len(query_words) - n + 1):
                ngrams.append(" ".join(query_words[i:i+n]))
        
        # Check for exact matches in response
        response_lower = response.lower()
        matches = sum(1 for ng in ngrams if ng in response_lower)
        
        if not ngrams:
            return 0.0
        
        memorization_ratio = matches / len(ngrams)
        
        # Weight by sensitivity: PII matches are worse
        pii_findings = self.pii_extractor.extract(query)
        pii_phrases = [f.value.lower() for f in pii_findings]
        pii_in_response = sum(1 for pii in pii_phrases if pii in response_lower)
        
        pii_leakage = pii_in_response / len(pii_phrases) if pii_phrases else 0.0
        
        # Combined risk
        risk = 0.6 * memorization_ratio + 0.4 * pii_leakage
        
        return min(1.0, risk)
    
    def _calculate_synthetic_epsilon(
        self,
        privacy_score: PrivacyScore,
        is_repeated: bool,
        user_state: Dict
    ) -> float:
        """
        Calculate a synthetic epsilon value as a proxy for privacy loss.
        
        This is NOT a true differential privacy epsilon, but a heuristic
        that increases with:
        - PII content in query
        - Query repetition
        - Cumulative exposure
        """
        base_epsilon = self.QUERY_EPSILON_COST
        
        # PII multiplier
        if privacy_score.query_pii_count > 0:
            base_epsilon *= self.PII_EPSILON_MULTIPLIER
        
        # High-risk PII multiplier
        high_risk_types = {"account_number", "credit_card", "pan_number", "aadhaar"}
        if any(t in privacy_score.query_pii_types for t in high_risk_types):
            base_epsilon *= 2.0
        
        # Repetition multiplier
        if is_repeated:
            base_epsilon *= self.REPETITION_EPSILON_MULTIPLIER
        
        # Time-based decay (queries spaced apart leak less)
        time_since_last = time.time() - user_state["last_query_time"]
        if time_since_last > 300:  # 5 minutes
            base_epsilon *= 0.8
        if time_since_last > 3600:  # 1 hour
            base_epsilon *= 0.5
        
        # Cumulative exposure penalty
        cumulative = user_state["cumulative_epsilon"]
        if cumulative > self.epsilon_budget * 0.5:
            base_epsilon *= 1.5
        if cumulative > self.epsilon_budget * 0.8:
            base_epsilon *= 2.0
        
        return round(base_epsilon, 4)
    
    def _calculate_information_leakage(
        self,
        query: str,
        response: str,
        privacy_score: PrivacyScore,
        memorization_risk: float
    ) -> float:
        """
        Calculate information leakage proxy score.
        
        Combines:
        - PII density
        - Query specificity (how targeted is the query)
        - Response memorization risk
        """
        # PII component (0-40)
        pii_component = min(40.0, privacy_score.query_pii_count * 5.0)
        
        # Query specificity (0-30)
        # More specific queries leak more information
        specificity = 0.0
        if re.search(r'\d{4,}', query):  # Contains numbers
            specificity += 10.0
        if len(query) > 200:  # Long query
            specificity += 10.0
        if len([w for w in query.split() if w.isupper()]) > 2:  # Many proper nouns
            specificity += 10.0
        
        # Memorization component (0-30)
        memo_component = memorization_risk * 30.0
        
        return min(100.0, pii_component + specificity + memo_component)
    
    def get_user_privacy_status(self, user_email: str) -> Dict[str, Any]:
        """Get current privacy status for a user."""
        state = self.user_privacy_state[user_email]
        
        budget_remaining = max(0, self.epsilon_budget - state["cumulative_epsilon"])
        budget_percentage = (state["cumulative_epsilon"] / self.epsilon_budget * 100) if self.epsilon_budget > 0 else 0
        
        return {
            "user_email": user_email,
            "cumulative_epsilon": round(state["cumulative_epsilon"], 4),
            "epsilon_budget": self.epsilon_budget,
            "budget_remaining": round(budget_remaining, 4),
            "budget_used_percentage": round(budget_percentage, 2),
            "query_count": state["query_count"],
            "total_pii_exposed": state["total_pii_exposed"],
            "unique_queries": len(state["query_hashes"]),
            "status": "EXCEEDED" if budget_remaining <= 0 else (
                "WARNING" if budget_percentage > 80 else "OK"
            )
        }
    
    def get_privacy_recommendations(self, user_email: str) -> List[str]:
        """Get personalized privacy recommendations."""
        status = self.get_user_privacy_status(user_email)
        recommendations = []
        
        if status["status"] == "EXCEEDED":
            recommendations.append(
                "CRITICAL: Your privacy budget has been exceeded. "
                "Please wait before submitting more queries."
            )
        elif status["status"] == "WARNING":
            recommendations.append(
                "WARNING: You are approaching your privacy budget limit. "
                "Consider reducing query frequency."
            )
        
        if status["total_pii_exposed"] > 10:
            recommendations.append(
                f"You have exposed {status['total_pii_exposed']} PII items. "
                "Review your queries for sensitive information."
            )
        
        if status["unique_queries"] < status["query_count"] * 0.5:
            recommendations.append(
                "Many of your queries are similar. "
                "Repeated queries increase information leakage risk."
            )
        
        if not recommendations:
            recommendations.append("Your privacy posture looks good. Keep it up!")
        
        return recommendations
    
    def generate_privacy_report(self, user_email: str) -> Dict[str, Any]:
        """Generate comprehensive privacy report for a user."""
        user_audits = [a for a in self.audit_log if a.user_email == user_email]
        
        if not user_audits:
            return {"error": "No audit records found for user"}
        
        risk_distribution = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        for audit in user_audits:
            risk_distribution[audit.risk_level] = risk_distribution.get(audit.risk_level, 0) + 1
        
        avg_risk_score = np.mean([a.overall_risk_score for a in user_audits])
        max_risk_score = max([a.overall_risk_score for a in user_audits])
        
        pii_types_exposed = set()
        for audit in user_audits:
            # Extract from query
            findings = self.pii_extractor.extract(audit.query)
            pii_types_exposed.update(f.pii_type for f in findings)
        
        return {
            "user_email": user_email,
            "total_interactions": len(user_audits),
            "current_status": self.get_user_privacy_status(user_email),
            "risk_distribution": risk_distribution,
            "average_risk_score": round(float(avg_risk_score), 2),
            "max_risk_score": round(float(max_risk_score), 2),
            "pii_types_exposed": list(pii_types_exposed),
            "recommendations": self.get_privacy_recommendations(user_email),
            "generated_at": datetime.utcnow().isoformat()
        }
    
    def reset_user_budget(self, user_email: str):
        """Reset privacy budget for a user (e.g., daily reset)."""
        if user_email in self.user_privacy_state:
            self.user_privacy_state[user_email]["cumulative_epsilon"] = 0.0
            self.user_privacy_state[user_email]["query_count"] = 0
            logger.info(f"Privacy budget reset for {user_email}")


def get_default_auditor() -> LLMPrivacyAuditor:
    """Get a default-configured privacy auditor."""
    return LLMPrivacyAuditor(
        epsilon_budget=10.0,
        enable_deduplication=True,
        enable_sanitization=True,
        enable_memorization_check=True
    )


if __name__ == "__main__":
    # Demo
    print("="*70)
    print("LLM PRIVACY AUDITOR DEMO")
    print("="*70)
    
    auditor = get_default_auditor()
    
    test_cases = [
        ("user1@example.com", "What is a good savings rate?", "A good savings rate is 20-30% of income."),
        ("user1@example.com", "My salary is Rs. 50,000. How much to save?", "You should save Rs. 10,000-15,000 monthly."),
        ("user1@example.com", "My PAN is ABCDE1234F and account 1234567890", "Please don't share PAN or account numbers."),
    ]
    
    for user, query, response in test_cases:
        print(f"\nUser: {user}")
        print(f"Query: {query[:60]}...")
        
        score, audit = auditor.audit_interaction(user, query, response)
        
        print(f"Risk: {audit.overall_risk_score}/100 ({audit.risk_level})")
        print(f"Synthetic ε: {audit.synthetic_epsilon_estimate}")
        print(f"Cumulative ε: {audit.cumulative_epsilon:.2f} / {auditor.epsilon_budget}")
        print(f"Response modified: {audit.response_modified}")
        if audit.sanitization_actions:
            print(f"Actions: {', '.join(audit.sanitization_actions)}")
    
    print("\n" + "="*70)
    print("User Privacy Status:")
    print("="*70)
    status = auditor.get_user_privacy_status("user1@example.com")
    print(json.dumps(status, indent=2))
    
    print("\nPrivacy Report:")
    report = auditor.generate_privacy_report("user1@example.com")
    print(json.dumps(report, indent=2))

