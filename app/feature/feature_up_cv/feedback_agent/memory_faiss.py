# -*- coding: utf-8 -*-
"""
Enhanced Agent Knowledge Memory - FAISS-based learned rules storage

Features:
- TTL (Time-To-Live) for rules
- Priority/confidence scoring
- Conflict detection and resolution
- Rule versioning
- Structured rule format support
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

from app.feature.feature_up_cv.vector_search.embedding_service import get_embedding_service, EMBEDDING_DIM

logger = logging.getLogger(__name__)

# Default TTL: 30 days
DEFAULT_RULE_TTL_DAYS = 30


class LearnedRule:
    """Structured rule format"""

    def __init__(
        self,
        rule_id: str,
        rule_type: str,
        condition: Dict,
        action: Dict,
        priority: int = 50,  # 0-100
        confidence: float = 0.5,  # 0.0-1.0
        ttl_days: int = DEFAULT_RULE_TTL_DAYS,
        created_at: str = None,
        source_case: str = None,
        parent_rule_id: str = None,
    ):
        self.rule_id = rule_id
        self.rule_type = rule_type  # FRESH_GRAD_PROJECT_BONUS, DOMAIN_EXPERIENCE_PENALTY, etc.
        self.condition = condition  # {"cv.is_student": True, "cv.projects.exists": True}
        self.action = action  # {"type": "bonus", "target": "experience_score", "value": 20}
        self.priority = priority  # Higher = more important
        self.confidence = confidence  # How confident the rule is correct
        self.ttl_days = ttl_days
        self.created_at = created_at or datetime.now().isoformat()
        self.source_case = source_case  # Which case this rule learned from
        self.parent_rule_id = parent_rule_id  # For rule versioning

    def is_expired(self) -> bool:
        """Check if rule has expired based on TTL"""
        try:
            created = datetime.fromisoformat(self.created_at)
            expiry = created + timedelta(days=self.ttl_days)
            return datetime.now() > expiry
        except:
            return False

    def get_rule_text(self) -> str:
        """Generate human-readable rule text for embedding"""
        condition_str = ", ".join(f"{k}={v}" for k, v in self.condition.items())
        action_str = f"{self.action.get('type', 'unknown')}: {self.action.get('target', '')}"
        return f"{self.rule_type} | Condition: {condition_str} | Action: {action_str}"

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "rule_type": self.rule_type,
            "condition": self.condition,
            "action": self.action,
            "priority": self.priority,
            "confidence": self.confidence,
            "ttl_days": self.ttl_days,
            "created_at": self.created_at,
            "source_case": self.source_case,
            "parent_rule_id": self.parent_rule_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LearnedRule":
        return cls(
            rule_id=data.get("rule_id", ""),
            rule_type=data.get("rule_type", ""),
            condition=data.get("condition", {}),
            action=data.get("action", {}),
            priority=data.get("priority", 50),
            confidence=data.get("confidence", 0.5),
            ttl_days=data.get("ttl_days", DEFAULT_RULE_TTL_DAYS),
            created_at=data.get("created_at"),
            source_case=data.get("source_case"),
            parent_rule_id=data.get("parent_rule_id"),
        )


class AgentKnowledgeMemory:
    """
    Enhanced Agent's learned rules using FAISS with:
    - TTL (Time-To-Live) for rules
    - Priority/confidence scoring
    - Conflict detection
    - Structured rule format
    """

    def __init__(self):
        self.index_dir = Path("app/feature/feature_up_cv/storage/faiss_indexes")
        self.index_dir.mkdir(parents=True, exist_ok=True)

        self.index_path = self.index_dir / "agent_rules_v2.faiss"
        self.meta_path = self.index_dir / "agent_rules_meta_v2.json"

        self.embedder = get_embedding_service()
        self.index: Optional[faiss.IndexFlatIP] = None
        self.rules: List[Dict] = []

        self._load()

    def _load(self):
        """Load rules from disk"""
        # Load meta
        if self.meta_path.exists():
            try:
                with open(self.meta_path, 'r', encoding='utf-8') as f:
                    self.rules = json.load(f)
                logger.info(f"[AgentMemory] Loaded {len(self.rules)} rules from disk")
            except Exception as e:
                logger.error(f"[AgentMemory] Failed to load meta: {e}")
                self.rules = []

        # Remove expired rules
        self.rules = [r for r in self.rules if not LearnedRule.from_dict(r).is_expired()]

        # Load index
        if FAISS_AVAILABLE and self.index_path.exists():
            try:
                self.index = faiss.read_index(str(self.index_path))
                # Rebuild if size mismatch
                if self.index.ntotal != len(self.rules):
                    logger.warning(f"[AgentMemory] Index size mismatch: {self.index.ntotal} vs {len(self.rules)}")
                    self._rebuild_index()
            except Exception as e:
                logger.error(f"[AgentMemory] Failed to load index: {e}")
                self._init_index()
        else:
            self._init_index()

    def _init_index(self):
        if FAISS_AVAILABLE:
            self.index = faiss.IndexFlatIP(EMBEDDING_DIM)

    def _rebuild_index(self):
        """Rebuild FAISS index from rules"""
        if not FAISS_AVAILABLE or not self.rules:
            self._init_index()
            return

        logger.info(f"[AgentMemory] Rebuilding FAISS index with {len(self.rules)} rules...")
        self.index = faiss.IndexFlatIP(EMBEDDING_DIM)

        texts = [LearnedRule.from_dict(r).get_rule_text() for r in self.rules]
        embeddings = self.embedder.encode_batch(texts, normalize=True)
        self.index.add(embeddings)

    def _save(self):
        """Save rules to disk"""
        with open(self.meta_path, 'w', encoding='utf-8') as f:
            json.dump(self.rules, f, ensure_ascii=False, indent=2)

        if FAISS_AVAILABLE and self.index is not None:
            faiss.write_index(self.index, str(self.index_path))

    def _check_conflicts(self, new_rule: LearnedRule) -> List[Dict]:
        """Detect conflicting rules"""
        conflicts = []

        for existing in self.rules:
            existing_rule = LearnedRule.from_dict(existing)

            # Same rule type
            if existing_rule.rule_type == new_rule.rule_type:
                # Check if conditions are mutually exclusive
                if self._are_conditions_mutually_exclusive(existing_rule.condition, new_rule.condition):
                    conflicts.append({
                        "existing_rule_id": existing_rule.rule_id,
                        "new_rule_id": new_rule.rule_id,
                        "type": "mutually_exclusive",
                        "suggestion": "Keep rule with higher priority"
                    })

        return conflicts

    def _are_conditions_mutually_exclusive(self, cond1: dict, cond2: dict) -> bool:
        """Check if two conditions are mutually exclusive"""
        # Check for opposite conditions
        for key in cond1:
            if key in cond2 and cond1[key] != cond2[key]:
                # Check if values are opposites
                if isinstance(cond1[key], bool) and isinstance(cond2[key], bool):
                    return True
                if isinstance(cond1[key], (int, float)) and isinstance(cond2[key], (int, float)):
                    if cond1[key] != cond2[key]:
                        return True
        return False

    def add_learned_rule(
        self,
        rule_text: str,
        context: str = "",
        rule_type: str = None,
        condition: dict = None,
        action: dict = None,
        priority: int = 50,
        confidence: float = 0.5,
        ttl_days: int = DEFAULT_RULE_TTL_DAYS,
        source_case: str = None,
        resolve_conflicts: bool = True,
    ) -> Dict:
        """
        Add a new learned rule with structured format.

        Returns: {
            "success": bool,
            "rule_id": str,
            "conflicts": list,
            "resolved": bool,
            "message": str
        }
        """
        if not rule_text.strip():
            return {"success": False, "message": "Empty rule text"}

        # Create structured rule
        import uuid
        rule_id = f"rule_{uuid.uuid4().hex[:8]}"

        rule = LearnedRule(
            rule_id=rule_id,
            rule_type=rule_type or self._infer_rule_type(rule_text),
            condition=condition or self._infer_condition(rule_text),
            action=action or self._infer_action(rule_text),
            priority=priority,
            confidence=confidence,
            ttl_days=ttl_days,
            source_case=source_case,
        )

        # Check for conflicts
        conflicts = self._check_conflicts(rule)
        result = {
            "success": True,
            "rule_id": rule_id,
            "conflicts": conflicts,
            "resolved": False,
            "message": ""
        }

        if conflicts and resolve_conflicts:
            # Resolve by keeping higher priority rule
            for conflict in conflicts:
                existing_idx = next(
                    (i for i, r in enumerate(self.rules) if r.get("rule_id") == conflict["existing_rule_id"]),
                    None
                )
                if existing_idx is not None:
                    existing_rule = LearnedRule.from_dict(self.rules[existing_idx])
                    if rule.priority > existing_rule.priority:
                        # New rule replaces old
                        logger.info(f"[AgentMemory] Replacing rule {conflict['existing_rule_id']} with new rule {rule_id}")
                        self.rules[existing_idx] = rule.to_dict()
                        result["resolved"] = True
                    else:
                        # Keep existing, skip new
                        result["success"] = False
                        result["message"] = f"Rule not added: existing rule has higher priority"
                        return result

        if result["success"]:
            self.rules.append(rule.to_dict())

            # Update index
            if FAISS_AVAILABLE and self.index is not None:
                embedding = self.embedder.encode(rule.get_rule_text(), normalize=True)
                embedding = embedding.reshape(1, -1).astype(np.float32)
                self.index.add(embedding)

            self._save()
            logger.info(f"[AgentMemory] Added rule {rule_id}. Total rules: {len(self.rules)}")

        return result

    def add_learned_rule_legacy(self, rule_text: str, context: str = ""):
        """Legacy method for backward compatibility"""
        return self.add_learned_rule(rule_text=rule_text, context=context)

    def _infer_rule_type(self, rule_text: str) -> str:
        """Infer rule type from text"""
        text_lower = rule_text.lower()

        if "fresh_grad" in text_lower or "project_bonus" in text_lower:
            return "FRESH_GRAD_PROJECT_BONUS"
        elif "domain_experience_penalty" in text_lower or "domain penalty" in text_lower:
            return "DOMAIN_EXPERIENCE_PENALTY"
        elif "severe_domain_mismatch" in text_lower or ("sales" in text_lower and "tech_backend" in text_lower):
            return "SEVERE_DOMAIN_MISMATCH"
        elif "internship" in text_lower or "entry_level" in text_lower:
            return "ENTRY_LEVEL_INTERNSHIP"
        elif "career_change" in text_lower:
            return "CAREER_CHANGE_PENALTY"
        else:
            return "GENERIC_RULE"

    def _infer_condition(self, rule_text: str) -> dict:
        """Infer condition from rule text"""
        text_lower = rule_text.lower()
        condition = {}

        if "is_student" in text_lower or "fresh_grad" in text_lower:
            condition["cv.is_student"] = True
        if "project" in text_lower:
            condition["cv.projects.exists"] = True
        if "internship" in text_lower:
            condition["cv.has_internship"] = True
        if "domain" in text_lower and "penalty" in text_lower:
            condition["cv.domain_differs"] = True
        if "career_change" in text_lower:
            condition["cv.domain_career_change"] = True

        return condition

    def _infer_action(self, rule_text: str) -> dict:
        """Infer action from rule text"""
        text_lower = rule_text.lower()
        action = {}

        if "bonus" in text_lower or "cộng" in text_lower or "+" in text_lower:
            action["type"] = "bonus"
            # Try to extract value
            import re
            bonus_match = re.search(r'(\d+)-(\d+)', text_lower)
            if bonus_match:
                action["min_value"] = int(bonus_match.group(1))
                action["max_value"] = int(bonus_match.group(2))
        elif "penalty" in text_lower or "giảm" in text_lower or "-" in text_lower:
            action["type"] = "penalty"
            import re
            penalty_match = re.search(r'(\d+)-(\d+)%', text_lower)
            if penalty_match:
                action["penalty_percent"] = (int(penalty_match.group(1)), int(penalty_match.group(2)))

        if "experience" in text_lower:
            action["target"] = "experience_score"
        elif "skill" in text_lower:
            action["target"] = "skills_score"

        return action

    def get_relevant_rules(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.5,
        include_expired: bool = False,
    ) -> List[Tuple[str, Dict]]:
        """
        Search for relevant rules based on semantic similarity.

        Returns: List of (rule_text, rule_metadata) tuples sorted by relevance
        """
        if not FAISS_AVAILABLE or self.index is None or self.index.ntotal == 0:
            return []

        if not query.strip():
            return []

        try:
            query_emb = self.embedder.encode(query, normalize=True)
            query_emb = query_emb.reshape(1, -1).astype(np.float32)

            actual_k = min(top_k * 2, self.index.ntotal)  # Fetch more to filter
            scores, indices = self.index.search(query_emb, actual_k)

            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0 and idx < len(self.rules):
                    rule_data = self.rules[idx]
                    rule = LearnedRule.from_dict(rule_data)

                    # Filter by threshold
                    if score < threshold:
                        continue

                    # Filter expired rules unless requested
                    if not include_expired and rule.is_expired():
                        continue

                    # Calculate effective score = similarity * priority * confidence
                    effective_score = score * (rule.priority / 100) * rule.confidence

                    results.append((rule.get_rule_text(), {
                        "rule_id": rule.rule_id,
                        "rule_type": rule.rule_type,
                        "priority": rule.priority,
                        "confidence": rule.confidence,
                        "similarity": float(score),
                        "effective_score": effective_score,
                        "action": rule.action,
                        "condition": rule.condition,
                        "source_case": rule.source_case,
                        "created_at": rule.created_at,
                        "is_expired": rule.is_expired(),
                    }))

            # Sort by effective score
            results.sort(key=lambda x: x[1]["effective_score"], reverse=True)

            # Return top_k
            return results[:top_k]

        except Exception as e:
            logger.error(f"[AgentMemory] Search failed: {e}")
            return []

    def get_relevant_rules_by_type(
        self,
        rule_type: str,
        top_k: int = 3,
    ) -> List[Dict]:
        """Get rules by type, sorted by priority"""
        matching = [r for r in self.rules
                   if LearnedRule.from_dict(r).rule_type == rule_type
                   and not LearnedRule.from_dict(r).is_expired()]

        matching.sort(key=lambda x: x.get("priority", 0), reverse=True)
        return matching[:top_k]

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID"""
        for i, r in enumerate(self.rules):
            if r.get("rule_id") == rule_id:
                self.rules.pop(i)
                self._rebuild_index()
                self._save()
                logger.info(f"[AgentMemory] Removed rule {rule_id}")
                return True
        return False

    def cleanup_expired(self) -> int:
        """Remove expired rules and return count"""
        before = len(self.rules)
        self.rules = [r for r in self.rules if not LearnedRule.from_dict(r).is_expired()]
        removed = before - len(self.rules)

        if removed > 0:
            self._rebuild_index()
            self._save()
            logger.info(f"[AgentMemory] Cleaned up {removed} expired rules")

        return removed

    def get_stats(self) -> dict:
        """Get memory statistics"""
        total = len(self.rules)
        active = sum(1 for r in self.rules if not LearnedRule.from_dict(r).is_expired())
        expired = total - active

        # Count by type
        by_type = {}
        for r in self.rules:
            rule = LearnedRule.from_dict(r)
            by_type[rule.rule_type] = by_type.get(rule.rule_type, 0) + 1

        # Average priority and confidence
        avg_priority = sum(r.get("priority", 0) for r in self.rules) / max(total, 1)
        avg_confidence = sum(r.get("confidence", 0.5) for r in self.rules) / max(total, 1)

        return {
            "total_rules": total,
            "active_rules": active,
            "expired_rules": expired,
            "by_type": by_type,
            "avg_priority": round(avg_priority, 1),
            "avg_confidence": round(avg_confidence, 2),
            "index_size": self.index.ntotal if self.index else 0,
        }


# Global instance
agent_memory = AgentKnowledgeMemory()
