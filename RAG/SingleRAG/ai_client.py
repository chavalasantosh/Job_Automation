"""
Indeed Auto-Apply AI Client (Ollama) - 10x Balanced
===================================================
Optimized for 2B models like Gemma 4. 
Uses structured context chunks to prevent 'Not specified' errors.
"""

import os
import json
import logging
import requests
from typing import Optional, Dict, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTEXT_FILE = os.path.join(BASE_DIR, "resume_context.json")
LOG_FILE = os.path.join(BASE_DIR, "ai_engine.log")
OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:e2b"

# Configure logging
logger = logging.getLogger("ai_fleet_client")
logger.setLevel(logging.INFO)
if not logger.handlers:
    rfh = logging.FileHandler(LOG_FILE)
    rfh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(rfh)

def load_structured_context():
    """Loads resume and organizes it for a 2B model's narrow attention span."""
    if not os.path.exists(CONTEXT_FILE): return ""
    try:
        with open(CONTEXT_FILE, 'r', encoding='utf-8') as f:
            full_text = json.load(f).get("full_text", "")
            
        # Extract specific sections to help the model find them
        lines = full_text.split('\n')
        summary = ""
        skills = ""
        projects = ""
        
        current_section = ""
        for line in lines:
            line_upper = line.upper().strip()
            if "SUMMARY" in line_upper: current_section = "S"
            elif "SKILLS" in line_upper: current_section = "SK"
            elif "PROJECTS" in line_upper or "EXPERIENCE" in line_upper: current_section = "P"
            
            if current_section == "S": summary += line + " "
            elif current_section == "SK": skills += line + " "
            elif current_section == "P": projects += line + " "
            
        structured = f"IDENTITY: Santosh Chavala, Senior AI/LLM Engineer.\n\nSKILLS BANK:\n{skills}\n\nPROJECT EVIDENCE:\n{projects}"
        return structured
    except: return ""

def solve_question(question: str) -> str:
    """Answers a job question with high accuracy using structured context."""
    context = load_structured_context()
    
    # 10x Simple Prompt - minimized noise
    prompt = (
        f"You are Santosh Chavala. Use this Resume Context to answer precisely:\n\n"
        f"{context}\n\n"
        f"Question: {question}\n"
        f"Strict Rule: Answer in 1-2 professional sentences using 'I'. If specific details aren't there, describe your AI Resume Automation project.\n"
        f"Output Answer:"
    )
    
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 150}
    }
    
    try:
        logger.info(f"AI Solving (10x): {question}")
        response = requests.post(OLLAMA_GENERATE_URL, json=payload, timeout=90)
        answer = response.json().get("response", "").strip()
        
        # Post-process: Remove AI conversational noise
        if "Answer:" in answer: answer = answer.split("Answer:")[-1].strip()
        
        logger.info(f"AI Success: {answer[:50]}...")
        return answer
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return "I have extensive experience building AI Resume Automation systems and semantic search engines."

if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "What is your main expertise?"
    print(solve_question(q))
