import json
from pathlib import Path

class AgentKnowledgeMemory:
    def __init__(self):
        self.memory_path = Path("app/feature/feature_up_cv/storage/faiss_indexes/agent_memory.json")
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        self.rules = self._load()

    def _load(self) -> list:
        if self.memory_path.exists():
            try:
                with open(self.memory_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save(self):
        with open(self.memory_path, 'w', encoding='utf-8') as f:
            json.dump(self.rules, f, ensure_ascii=False, indent=2)

    def add_learned_rule(self, rule_text: str, context: str = ""):
        self.rules.append({
            "rule": rule_text,
            "context": context
        })
        self._save()

    def get_relevant_rules(self, query: str = "", top_k: int = 3) -> list:
        return [r["rule"] for r in self.rules[-top_k:]]

agent_memory = AgentKnowledgeMemory()
