"""
Industrial Resume RAG Engine
============================
Clean, class-based Retrieval Augmented Generation for Santosh Chavala's Resume.
Specifically tuned for Gemma 4 2B on local Ollama.

FIXES APPLIED:
  - H5: Hardcoded absolute path replaced with Path-relative resolution
  - M6: Bare `except: return ""` now logs the error before returning
"""

import os
import json
import logging
import requests
from pathlib import Path
from typing import Optional, Dict, Any
from pypdf import PdfReader


class ResumeRAG:
    def __init__(self, resume_path: str = None):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))

        # FIX H5: Use Path-relative resolution — works on any machine/user
        if resume_path:
            self.resume_path = resume_path
        else:
            # Walk up: SingleRAG -> RAG -> Nowcurry root -> LinkieDin
            self.resume_path = str(
                Path(__file__).resolve().parent.parent.parent
                / "LinkieDin"
                / "SANTOSH CHAVALA.pdf"
            )

        self.context_file = os.path.join(self.base_dir, "resume_context.json")
        self.log_file     = os.path.join(self.base_dir, "rag_engine.log")
        self.ollama_url   = "http://localhost:11434/api/generate"
        self.model        = "gemma4:e2b"

        self._setup_logging()

    def _setup_logging(self):
        self.logger = logging.getLogger("ResumeRAG")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            try:
                rfh = logging.FileHandler(self.log_file, encoding='utf-8')
                rfh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
                self.logger.addHandler(rfh)
            except (PermissionError, OSError):
                pass

    def refresh_context(self) -> bool:
        """Extracts text from PDF and updates the local RAG context."""
        if not os.path.exists(self.resume_path):
            self.logger.error(f"Resume not found at {self.resume_path}")
            return False
        try:
            reader   = PdfReader(self.resume_path)
            full_text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    full_text += extracted + "\n"

            data = {
                "file_name":      os.path.basename(self.resume_path),
                "full_text":      full_text.strip(),
                "last_extracted": os.path.getmtime(self.resume_path)
            }
            with open(self.context_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            self.logger.info("RAG Context Refreshed successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Context Refresh Failed: {e}")
            return False

    def _get_structured_content(self) -> str:
        """Loads and structures the resume for narrow-context LLMs."""
        if not os.path.exists(self.context_file):
            if not self.refresh_context():
                return ""

        try:
            with open(self.context_file, 'r', encoding='utf-8') as f:
                full_text = json.load(f).get("full_text", "")

            # Smart Segmenting
            lines    = full_text.split('\n')
            skills, projects = "", ""
            current  = ""
            for line in lines:
                l = line.upper().strip()
                if "SKILLS" in l:
                    current = "S"
                elif "PROJECTS" in l or "EXPERIENCE" in l:
                    current = "P"

                if current == "S":
                    skills   += line + " "
                elif current == "P":
                    projects += line + " "

            return (
                f"IDENTITY: Santosh Chavala, AI/LLM Engineer.\n\n"
                f"SKILLS:\n{skills}\n\n"
                f"EXPERIENCE:\n{projects}"
            )
        except Exception as e:
            # FIX M6: Log the error — don't swallow silently
            self.logger.error(f"Failed to load structured content: {e}")
            return ""

    def query(self, question: str) -> str:
        """Queries the RAG engine with a job-specific question."""
        context = self._get_structured_content()
        prompt  = (
            f"Context:\n{context}\n\n"
            f"Question: {question}\n"
            f"Constraint: Answer as Santosh in 1 concise sentence. Output text only.\n"
            "Answer:"
        )

        payload = {
            "model":   self.model,
            "prompt":  prompt,
            "stream":  False,
            "options": {"temperature": 0.1}
        }

        try:
            self.logger.info(f"RAG Query: {question}")
            r      = requests.post(self.ollama_url, json=payload, timeout=90)
            answer = r.json().get("response", "").strip()
            self.logger.info(f"RAG Answer: {answer[:60]}...")
            return answer
        except Exception as e:
            self.logger.error(f"RAG Query Error: {e}")
            return "I have extensive experience in AI/LLM development as detailed in my resume."

    def query_with_context(self, question: str, context: str) -> str:
        """
        Queries Gemma with an explicitly provided context string.
        Used by MultiRAG to pass combined Resume + JD context cleanly.
        """
        prompt = (
            f"Context:\n{context}\n\n"
            f"Question: {question}\n"
            f"Constraint: Answer as Santosh in 1 concise sentence. Output text only.\n"
            "Answer:"
        )
        payload = {
            "model":   self.model,
            "prompt":  prompt,
            "stream":  False,
            "options": {"temperature": 0.1}
        }
        try:
            self.logger.info(f"MultiRAG Query: {question}")
            r      = requests.post(self.ollama_url, json=payload, timeout=90)
            answer = r.json().get("response", "").strip()
            return answer
        except Exception as e:
            self.logger.error(f"MultiRAG Query Error: {e}")
            return "I have strong relevant experience as per my resume."


if __name__ == "__main__":
    rag = ResumeRAG()
    # rag.refresh_context()
    print(rag.query("What is your expertise in Generative AI?"))
