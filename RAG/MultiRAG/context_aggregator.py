"""
Multi-RAG Context Aggregator
============================
Aggregates Resume RAG + Job Description context for targeted question answering.

FIXES APPLIED:
  - M4: Replaced absolute import path with relative import — works from any CWD
"""

import logging
from typing import Optional

# FIX M4: Use relative import — absolute `from RAG.SingleRAG...` breaks
#          when this module is imported from a parent directory
try:
    from RAG.SingleRAG.resume_engine import ResumeRAG
except ImportError:
    # Fallback for when running directly from RAG/MultiRAG/
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from RAG.SingleRAG.resume_engine import ResumeRAG

logger = logging.getLogger("MultiRAG")


class MultiRAG:
    def __init__(self):
        self.resume_rag = ResumeRAG()

    def aggregate_context(self, jd_text: str) -> str:
        """Combines resume with JD into a single targeted context block."""
        resume_context = self.resume_rag._get_structured_content()
        return (
            "--- PERSONAL BACKGROUND ---\n"
            f"{resume_context}\n\n"
            "--- TARGET JOB DESCRIPTION ---\n"
            f"{jd_text}\n\n"
            "--- AGENT INSTRUCTION ---\n"
            "Identify overlapping skills. Highlight experience that directly addresses the JD."
        )

    def solve_targeted_question(self, question: str, jd_text: str) -> str:
        """
        Answers a question using both resume AND job description context.
        Uses explicit context-aware query (no monkeypatching).
        """
        combined_context = self.aggregate_context(jd_text)
        return self.resume_rag.query_with_context(question, combined_context)


if __name__ == "__main__":
    mrag   = MultiRAG()
    print("Multi-RAG Aggregator initialized.")
    result = mrag.solve_targeted_question(
        "What experience do you have with RAG pipelines?",
        "We need an LLM engineer with RAG and vector DB experience."
    )
    print(result)
