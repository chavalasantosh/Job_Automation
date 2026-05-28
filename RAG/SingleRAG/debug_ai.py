import requests

URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:e2b"

context = """
SANTOSH CHAVALA - AI/LLM Engineer
SKILLS: Generative AI & NLP, Transformers, RAG.
EXPERIENCE: AI Resume Automation System (2024-2025). Built BERT + Sentence Transformers matching.
"""

prompt = f"Using ONLY the following resume context, answer: 'What is your experience with Generative AI?'\n\nCONTEXT:\n{context}\n\nAnswer:"

payload = {
    "model": MODEL,
    "prompt": prompt,
    "stream": False,
    "options": {"temperature": 0.1}
}

try:
    print("Testing simple generate mode...")
    r = requests.post(URL, json=payload, timeout=30)
    print(r.json().get("response"))
except Exception as e:
    print(f"Error: {e}")
