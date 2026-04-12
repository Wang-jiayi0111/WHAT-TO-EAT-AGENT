"""
Prompts package for the WHAT-TO-EAT-AGENT system.
"""
from .router import ROUTER_PROMPT
from .researcher import RESEARCHER_PROMPT
from .logistics import LOGISTICS_PROMPT

__all__ = ["ROUTER_PROMPT", "RESEARCHER_PROMPT", "LOGISTICS_PROMPT"]