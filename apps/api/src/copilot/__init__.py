"""Source-grounded meteorological copilot utilities.

The copilot is deliberately separate from the numerical nowcasting and alert
pipelines.  It can explain data and retrieve operational guidance, but it does
not create or approve an official warning.
"""

from .rag import answer_question, get_suggestions, retrieve_knowledge

__all__ = ["answer_question", "get_suggestions", "retrieve_knowledge"]
