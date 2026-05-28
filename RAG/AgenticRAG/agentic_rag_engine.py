"""
Agentic RAG Engine — NowCurry Infinity Edition
===============================================
Full plan-and-execute RAG loop for autonomous job application reasoning.

Architecture:
  1. PLAN   — Extract screening questions from job description text
  2. ROUTE  — Decide: CareerGraph (structured) vs MultiRAG (open-ended)
  3. EXECUTE— Query the appropriate RAG component
  4. CACHE  — Persist answers keyed by question hash (survives Ollama downtime)
  5. RETURN — Structured answers dict ready for chatbot solver / apply payload

Usage:
    rag = AgenticRAG()
    answers = rag.plan_and_execute(job_id="12345678", jd_text="...job description...")
    # answers = {"What is your notice period?": "I can join within 30 days.", ...}
"""

import os
import re
import json
import hashlib
import logging
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger("AgenticRAG")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    _sh = logging.StreamHandler()
    _sh.setFormatter(logging.Formatter('%(asctime)s [AgenticRAG] %(levelname)s - %(message)s'))
    logger.addHandler(_sh)
    logger.propagate = False


# ── Paths ─────────────────────────────────────────────────────────────────────
_THIS_DIR    = Path(__file__).resolve().parent
_CACHE_FILE  = _THIS_DIR / "answer_cache.json"
_LOG_FILE    = _THIS_DIR / "agentic_rag.log"

# ── Common screening question patterns ────────────────────────────────────────
_QUESTION_PATTERNS = [
    r"(?:what is|what'?s) your (?:current |expected |)(?:notice period|joining time)[^.?!]*[.?!]?",
    r"(?:what is|what'?s) your (?:current |expected |)(?:ctc|salary|compensation|package)[^.?!]*[.?!]?",
    r"(?:how many years?|how much) (?:of )?experience[^.?!]*[.?!]?",
    r"(?:are you|are you currently) (?:working|employed|available)[^.?!]*[.?!]?",
    r"(?:can you|do you) (?:work|relocate|travel)[^.?!]*[.?!]?",
    r"(?:what is|what'?s) your (?:highest |)(?:qualification|education|degree)[^.?!]*[.?!]?",
    r"(?:describe|tell us about|explain) your (?:experience with|background in|expertise in)[^.?!]*[.?!]?",
    r"(?:why are you|what made you) (?:interested|applying|looking)[^.?!]*[.?!]?",
    r"(?:what|which) (?:tools?|technologies?|frameworks?|languages?) (?:do you|have you) (?:use|used|work|worked with)[^.?!]*[.?!]?",
]

# ── Structured question tags that map best to CareerGraph ─────────────────────
_STRUCTURED_KEYWORDS = [
    "notice period", "joining", "ctc", "salary", "compensation", "package",
    "experience", "years", "qualification", "education", "degree", "available",
    "relocate", "travel", "work from home", "remote", "shift",
]


class AgenticRAG:
    """
    Plan-and-Execute Agentic RAG for NowCurry job application pipeline.
    Orchestrates CareerGraph + MultiRAG for end-to-end screening reasoning.
    """

    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model      = "gemma4:e2b"
        self._cache: Dict[str, str] = self._load_cache()
        self._ollama_up: Optional[bool] = None  # Lazy health check

        # Lazy-load RAG components (avoid import errors if ran standalone)
        self._career_graph = None
        self._multi_rag    = None

        # File logger (in addition to stream)
        try:
            _fh = logging.FileHandler(str(_LOG_FILE), encoding='utf-8')
            _fh.setFormatter(logging.Formatter('%(asctime)s [AgenticRAG] %(levelname)s - %(message)s'))
            logger.addHandler(_fh)
        except (PermissionError, OSError):
            pass

    # ── Cache Management ──────────────────────────────────────────────────────

    def _load_cache(self) -> Dict[str, str]:
        if _CACHE_FILE.exists():
            try:
                with open(_CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Cache load failed: {e}. Starting fresh.")
        return {}

    def _save_cache(self):
        try:
            with open(_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")

    def _cache_key(self, question: str) -> str:
        """Stable cache key from question text (lowercased, whitespace-normalized)."""
        normalized = re.sub(r'\s+', ' ', question.lower().strip())
        return hashlib.md5(normalized.encode()).hexdigest()

    def _get_cached(self, question: str) -> Optional[str]:
        return self._cache.get(self._cache_key(question))

    def _set_cached(self, question: str, answer: str):
        self._cache[self._cache_key(question)] = answer
        self._save_cache()

    # ── Ollama Health ─────────────────────────────────────────────────────────

    def _check_ollama(self) -> bool:
        """Quick health check — result cached for the session."""
        if self._ollama_up is not None:
            return self._ollama_up
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=3)
            self._ollama_up = r.status_code == 200
        except Exception:
            self._ollama_up = False
        if not self._ollama_up:
            logger.warning("Ollama is offline — AgenticRAG will use cached answers only.")
        return self._ollama_up

    # ── RAG Component Access ──────────────────────────────────────────────────

    def _get_career_graph(self):
        if self._career_graph is None:
            try:
                import sys
                sys.path.insert(0, str(_THIS_DIR.parent.parent))
                from RAG.SingleRAG.career_graph import CareerGraph
                self._career_graph = CareerGraph()
            except Exception as e:
                logger.error(f"CareerGraph load failed: {e}")
                self._career_graph = False
        return self._career_graph if self._career_graph is not False else None

    def _get_multi_rag(self):
        if self._multi_rag is None:
            try:
                import sys
                sys.path.insert(0, str(_THIS_DIR.parent.parent))
                from RAG.MultiRAG.context_aggregator import MultiRAG
                self._multi_rag = MultiRAG()
            except Exception as e:
                logger.error(f"MultiRAG load failed: {e}")
                self._multi_rag = False
        return self._multi_rag if self._multi_rag is not False else None

    # ── Phase 1: PLAN — Extract Questions ────────────────────────────────────

    def extract_questions(self, jd_text: str) -> List[str]:
        """
        Extract probable screening questions from a job description.
        Uses regex patterns first (fast, offline), then optionally Gemma for deeper extraction.
        """
        questions = []
        text_lower = jd_text.lower()

        # Regex-based extraction (always runs)
        for pattern in _QUESTION_PATTERNS:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            for m in matches:
                q = m.strip().rstrip('.').capitalize()
                if q and q not in questions:
                    questions.append(q)

        # Common canned questions that appear in Naukri chatbot flows
        canned = [
            "What is your current CTC?",
            "What is your expected CTC?",
            "What is your notice period?",
            "Are you open to relocate?",
            "What is your current location?",
            "How many years of experience do you have?",
        ]
        for q in canned:
            if any(kw in jd_text.lower() for kw in q.lower().split()):
                if q not in questions:
                    questions.append(q)

        # If Ollama is available and JD is rich, ask Gemma to extract more
        if self._check_ollama() and len(jd_text) > 200 and len(questions) < 3:
            try:
                prompt = (
                    "Extract up to 5 screening questions a recruiter would ask based on this JD.\n"
                    "Return ONLY a JSON array of question strings. Example: [\"Q1?\", \"Q2?\"]\n\n"
                    f"JD:\n{jd_text[:1500]}"
                )
                r    = requests.post(
                    self.ollama_url,
                    json={"model": self.model, "prompt": prompt, "stream": False, "format": "json"},
                    timeout=30
                )
                raw  = r.json().get("response", "[]")
                extracted = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(extracted, list):
                    for q in extracted:
                        if isinstance(q, str) and q.strip() and q not in questions:
                            questions.append(q.strip())
            except Exception as e:
                logger.debug(f"Gemma question extraction failed: {e}")

        logger.info(f"PLAN: Extracted {len(questions)} screening questions")
        return questions[:8]  # Cap at 8 to prevent timeout loops

    # ── Phase 2: ROUTE ────────────────────────────────────────────────────────

    def _route(self, question: str) -> str:
        """
        Decide which RAG component to use.
        Returns 'career_graph' for structured/factual Qs, 'multi_rag' for open-ended.
        """
        q_lower = question.lower()
        if any(kw in q_lower for kw in _STRUCTURED_KEYWORDS):
            return "career_graph"
        return "multi_rag"

    # ── Phase 3: EXECUTE ──────────────────────────────────────────────────────

    def _execute(self, question: str, jd_text: str) -> str:
        """Run the appropriate RAG component for one question."""
        # Check cache first
        cached = self._get_cached(question)
        if cached:
            logger.debug(f"Cache hit for: {question[:50]}")
            return cached

        # If Ollama is offline, return a safe fallback
        if not self._check_ollama():
            return self._safe_fallback(question)

        route = self._route(question)
        answer = ""

        if route == "career_graph":
            cg = self._get_career_graph()
            if cg:
                answer = cg.solve_question(question, job_context=jd_text[:500])

        if not answer:
            # Fallback to MultiRAG for any route or on CareerGraph failure
            mrag = self._get_multi_rag()
            if mrag:
                answer = mrag.solve_targeted_question(question, jd_text)

        if not answer:
            answer = self._safe_fallback(question)

        # Cache the answer
        if answer:
            self._set_cached(question, answer)

        return answer

    def _safe_fallback(self, question: str) -> str:
        """Returns a sensible static fallback when Ollama is down."""
        q_lower = question.lower()
        if "notice" in q_lower or "joining" in q_lower:
            return "I can join within 30 days of offer acceptance."
        if "ctc" in q_lower or "salary" in q_lower or "compensation" in q_lower:
            return "I am looking for a competitive package aligned with market standards."
        if "experience" in q_lower or "years" in q_lower:
            return "I have 3+ years of experience in AI/ML and LLM engineering."
        if "relocat" in q_lower:
            return "Yes, I am open to relocation based on the opportunity."
        if "remote" in q_lower or "work from home" in q_lower:
            return "Yes, I can work remotely or from office as required."
        if "qualification" in q_lower or "education" in q_lower or "degree" in q_lower:
            return "I hold a B.Tech degree in Computer Science."
        return "I have strong relevant experience and would be happy to discuss further."

    # ── Main Entry Point ──────────────────────────────────────────────────────

    def plan_and_execute(self, job_id: str, jd_text: str = "") -> Dict[str, str]:
        """
        Full agentic loop: Plan → Route → Execute → Cache → Return.

        Args:
            job_id:   Naukri job ID (used for logging)
            jd_text:  Raw job description text

        Returns:
            Dict mapping question → answer strings
        """
        logger.info(f"=[AgenticRAG]= Starting plan-and-execute for job: {job_id}")

        if not jd_text or not jd_text.strip():
            logger.info(f"Job {job_id}: No JD text provided — running standard canned Qs")
        
        answers: Dict[str, str] = {}

        # Phase 1: Extract questions
        questions = self.extract_questions(jd_text)
        if not questions:
            logger.info(f"Job {job_id}: No questions extracted — skipping RAG")
            return {}

        # Phase 3: Execute RAG for each question
        for q in questions:
            try:
                answer = self._execute(q, jd_text)
                answers[q] = answer
                logger.info(f"  Q: {q[:60]}")
                logger.info(f"  A: {answer[:80]}")
            except Exception as e:
                logger.error(f"  Failed to answer '{q[:50]}': {e}")
                answers[q] = self._safe_fallback(q)

        logger.info(f"=[AgenticRAG]= Done for {job_id}: {len(answers)} answers prepared")
        return answers


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample_jd = """
    We are looking for an experienced AI/ML Engineer with 3-5 years of experience
    in building LLM-based applications. Strong knowledge of Python, RAG pipelines,
    and vector databases required. Must be open to relocation to Bangalore.
    What is your current CTC? What is your expected CTC?
    What is your notice period? Are you open to relocate to Bangalore?
    """

    engine  = AgenticRAG()
    results = engine.plan_and_execute("TEST_JOB_001", sample_jd)

    print("\n" + "="*60)
    print("AGENTIC RAG RESULTS")
    print("="*60)
    for q, a in results.items():
        print(f"\nQ: {q}")
        print(f"A: {a}")
