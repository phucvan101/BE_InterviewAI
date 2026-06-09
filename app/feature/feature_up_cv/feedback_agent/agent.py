import logging
from typing import Any, List, Optional, Dict, Type
from pydantic import BaseModel, Field
from langchain_core.language_models.llms import LLM
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.tools import BaseTool

from app.feature.feature_up_cv.core.gemini_client import generate_content
from app.feature.feature_up_cv.feedback_agent.prompts import FeedbackEvaluation, SYSTEM_PROMPT_EVALUATOR
from app.feature.feature_up_cv.feedback_agent.memory_faiss import agent_memory
from app.feature.feature_up_cv.feedback_agent.synonym_manager import synonym_manager

logger = logging.getLogger(__name__)

# ── 1. Custom LangChain LLM Wrapper ───────────────────────────────────────────────────
class GeminiLangChainLLM(LLM):
    """
    A custom LangChain LLM wrapper that routes calls through our robust gemini_client.generate_content.
    This preserves multi-key rotation, exponential backoff, and exception classification.
    """
    temperature: float = 0.0

    @property
    def _llm_type(self) -> str:
        return "gemini_custom"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        # Stop sequences are not natively handled here, but we can pass them if gemini supports it.
        # Call generate_content directly
        return generate_content(prompt=prompt, step="langchain_agent_evaluation")

# ── 2. LangChain Custom Tools ────────────────────────────────────────────────────────
class YAMLAddingSynonymTool(BaseTool):
    name: str = "yaml_adding_synonym"
    description: str = "Use this tool to add new synonym mappings for skills into the skill_synonyms.yaml file."

    def _run(self, new_synonyms: List[Dict[str, str]]) -> str:
        if not new_synonyms:
            return "No synonyms provided."
        try:
            success = synonym_manager.add_synonyms(new_synonyms)
            if success:
                return f"Successfully added synonyms: {new_synonyms} to YAML."
            return "Synonyms already exist or failed to write to YAML."
        except Exception as e:
            return f"Error adding synonyms: {str(e)}"

class FAISSAddingRuleTool(BaseTool):
    name: str = "faiss_adding_rule"
    description: str = "Use this tool to store a learned rule or semantic concept in the FAISS memory database."

    def _run(self, rule_text: str, context: str = "") -> str:
        if not rule_text:
            return "No rule text provided."
        try:
            agent_memory.add_learned_rule(rule_text=rule_text, context=context)
            return f"Successfully saved rule '{rule_text}' to FAISS Memory."
        except Exception as e:
            return f"Error saving rule to FAISS: {str(e)}"

# ── 3. LangChain Agent Orchestrator ───────────────────────────────────────────────────
class SelfCorrectingFeedbackAgent:
    def __init__(self):
        self.llm = GeminiLangChainLLM()
        self.parser = PydanticOutputParser(pydantic_object=FeedbackEvaluation)
        
        # Build Prompt Template with Output Instructions
        self.prompt_template = PromptTemplate(
            template=(
                "{system_prompt}\n\n"
                "Format Instructions:\n{format_instructions}\n\n"
                "[RAW_CV_TEXT]:\n{cv_text}\n\n"
                "[JD_TEXT]:\n{jd_text}\n\n"
                "[USER_FEEDBACK]:\n{feedback_text}\n"
            ),
            input_variables=["system_prompt", "cv_text", "jd_text", "feedback_text"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()},
        )
        
        # Define Tools
        self.synonym_tool = YAMLAddingSynonymTool()
        self.faiss_tool = FAISSAddingRuleTool()

    async def run(self, cv_text: str, jd_text: str, feedback_text: str) -> FeedbackEvaluation:
        """Runs the LangChain agent loop to evaluate feedback and invoke tools."""
        logger.info("[LangChain Agent] Starting feedback analysis...")
        
        # 1. Format prompt
        formatted_prompt = self.prompt_template.format(
            system_prompt=SYSTEM_PROMPT_EVALUATOR,
            cv_text=cv_text[:4000],
            jd_text=jd_text[:2000],
            feedback_text=feedback_text
        )
        
        # 2. Call LLM via our custom LangChain wrapper
        raw_response = await self.llm.ainvoke(formatted_prompt)
        
        # 3. Parse output to structured Pydantic model
        parsed_output: FeedbackEvaluation = self.parser.parse(raw_response)
        
        # 4. Trigger Tools conditionally based on Agent's decisions
        if parsed_output.is_valid_complaint:
            logger.info("[LangChain Agent] Complaint is valid! Executing tools...")
            
            # Action A: Add Synonyms if proposed
            if parsed_output.new_synonyms:
                tool_result = self.synonym_tool.run(parsed_output.new_synonyms)
                logger.info(f"[LangChain Agent] Tool: {tool_result}")
            
            # Action B: Add Learned Rule to FAISS if proposed
            if parsed_output.learned_rule:
                tool_result = self.faiss_tool.run(
                    rule_text=parsed_output.learned_rule,
                    context=feedback_text
                )
                logger.info(f"[LangChain Agent] Tool: {tool_result}")
                
        else:
            logger.info("[LangChain Agent] Complaint is marked invalid by LLM. Skipping tools.")
            
        return parsed_output

# Global Agent instance
feedback_agent = SelfCorrectingFeedbackAgent()
