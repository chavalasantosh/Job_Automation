import os
import json
import logging
import requests
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class CareerGraph:
    """
    INDUSTRIAL LOCAL CAREER GRAPH - Infinity Edition.
    Transforms resume data into a semantic entity-relation map using local Gemma.
    Performs 'Path Reasoning' for screening questions without external data transit.

    FIXES APPLIED:
      - C5: Bare `except:` replaced with logged exception handling throughout
      - M3: Resume text truncation increased from 1500 → 3500 chars (Gemma 2B handles it)
    """

    def __init__(self, model: str = "gemma4:e2b"):
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model      = model
        self.graph_file = os.path.join(os.path.dirname(__file__), "career_graph.json")

        # FIX H5 consistency: use Path-relative resolution for resume
        from pathlib import Path
        self.resume_path = str(
            Path(__file__).resolve().parent.parent.parent
            / "LinkieDin"
            / "SANTOSH CHAVALA.pdf"
        )
        self.graph = self._load_graph()

        # Auto-Bootstrap if empty and resume exists
        if not self.graph.get("nodes") and os.path.exists(self.resume_path):
            self._auto_bootstrap()

    def _load_graph(self) -> Dict[str, Any]:
        if os.path.exists(self.graph_file):
            try:
                with open(self.graph_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                # FIX C5: Log error instead of silently swallowing
                logger.error(f"CareerGraph: Failed to load graph file: {e}")
        return {"nodes": [], "edges": []}

    def _save_graph(self):
        try:
            with open(self.graph_file, 'w') as f:
                json.dump(self.graph, f, indent=4)
        except Exception as e:
            logger.error(f"CareerGraph: Failed to save graph: {e}")

    def _auto_bootstrap(self):
        logger.info("Infinity Brain: Local Graph empty. Extracting career semantics via Gemma...")
        from pypdf import PdfReader
        try:
            reader = PdfReader(self.resume_path)
            text   = "".join([p.extract_text() or "" for p in reader.pages])
            self.build_from_resume(text)
        except Exception as e:
            # FIX C5: Was bare except — now logs properly
            logger.error(f"CareerGraph: Bootstrap failed: {e}")

    def build_from_resume(self, resume_text: str):
        """Industrial local entity extraction optimized for Gemma 2B."""
        print(f">>> Infinity Brain: Reading your resume ({len(resume_text)} chars)...")

        # FIX M3: Increased truncation from 1500 → 3500 chars
        truncated = resume_text[:3500]

        prompt = (
            "Summarize this resume into a JSON list of Skills and Experience.\n"
            'Format: {"nodes": [{"id": "skill_name", "label": "Skill"}, ...]}\n\n'
            f"Resume Text:\n{truncated}"
        )

        payload = {
            "model":  self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        try:
            print(">>> Local LLM (Gemma) is building your career profile...")
            r            = requests.post(self.ollama_url, json=payload, timeout=120)
            raw_response = r.json().get("response", "{}")

            try:
                data = json.loads(raw_response)
            except json.JSONDecodeError:
                logger.warning("CareerGraph: Gemma returned non-JSON response. Using fallback graph.")
                data = {}

            if not data.get("nodes"):
                data["nodes"] = [{"id": "santosh_chavala", "label": "AI/LLM Engineer"}]

            self.graph = data
            self._save_graph()
            print(f">| Success: Mapped {len(self.graph.get('nodes', []))} nodes to Career Graph.")
            logger.info("Career Graph Built Successfully.")
        except Exception as e:
            # FIX C5: Was bare except with silent fallback — now properly logged
            logger.error(f"CareerGraph: build_from_resume failed: {e}")
            print(f">| Fallback: Creating default Career Graph. (Error: {e})")
            self.graph = {"nodes": [{"id": "santosh_chavala", "label": "AI/LLM Engineer"}]}
            self._save_graph()

    def solve_question(self, question: str, job_context: str = "") -> str:
        """Local path reasoning for screening questions."""
        logger.info(f"Local Brain: Solving screening question -> {question}")

        prompt = (
            f"PROFESSIONAL GRAPH:\n{json.dumps(self.graph)}\n\n"
            f"QUESTION: {question}\n"
            "INSTRUCTION: Answer in 1 short sentence as Santosh. Be professional."
        )
        if job_context:
            prompt = f"JOB CONTEXT:\n{job_context}\n\n" + prompt

        payload = {
            "model":   self.model,
            "prompt":  prompt,
            "stream":  False,
            "options": {"temperature": 0.1}
        }
        try:
            r = requests.post(self.ollama_url, json=payload, timeout=60)
            return r.json().get("response", "").strip()
        except Exception as e:
            # FIX C5: Was bare except — now logged
            logger.error(f"CareerGraph: solve_question failed: {e}")
            return "I have extensive experience in this area as per my resume."
