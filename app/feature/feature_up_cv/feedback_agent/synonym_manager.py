import os
from pathlib import Path
from typing import List, Dict
import logging
from ruamel.yaml import YAML

logger = logging.getLogger(__name__)

class SynonymManager:
    def __init__(self, yaml_path: str = "app/feature/feature_up_cv/scoring/skill_synonyms.yaml"):
        self.yaml_path = Path(yaml_path)
        self.yaml = YAML()
        # Preserve quotes and formatting
        self.yaml.preserve_quotes = True
        self.yaml.indent(mapping=2, sequence=4, offset=2)

    def add_synonyms(self, new_synonyms: List[Dict[str, str]]) -> bool:
        """
        Adds new synonyms to the yaml file safely.
        new_synonyms format: [{"base_skill": "react", "synonym": "next.js"}]
        """
        if not new_synonyms:
            return False

        try:
            if not self.yaml_path.exists():
                logger.error(f"[SynonymManager] YAML file not found at {self.yaml_path}")
                return False

            with open(self.yaml_path, 'r', encoding='utf-8') as f:
                data = self.yaml.load(f)

            if data is None:
                data = {}

            updated = False
            for item in new_synonyms:
                base = item.get("base_skill", "").strip().lower()
                syn = item.get("synonym", "").strip().lower()

                if not base or not syn:
                    continue

                # Ensure base skill exists in yaml, if not create it
                if base not in data:
                    data[base] = [base]
                
                # Check if synonym is already in the list for this base skill
                if syn not in [str(x).lower() for x in data[base]]:
                    data[base].append(syn)
                    updated = True
                    logger.info(f"[SynonymManager] Added synonym '{syn}' to base skill '{base}'")

            if updated:
                with open(self.yaml_path, 'w', encoding='utf-8') as f:
                    self.yaml.dump(data, f)
                logger.info(f"[SynonymManager] Successfully updated {self.yaml_path.name}")
                return True
            
            return False

        except Exception as e:
            logger.error(f"[SynonymManager] Error updating synonyms: {e}")
            return False

synonym_manager = SynonymManager()
