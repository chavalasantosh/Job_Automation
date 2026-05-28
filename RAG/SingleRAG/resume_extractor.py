import os
import json
from pypdf import PdfReader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESUME_PATH = r"c:\Users\SCHAVALA\Downloads\codes\Nowcurry\LinkieDin\SANTOSH CHAVALA.pdf"
OUTPUT_PATH = os.path.join(BASE_DIR, "resume_context.json")

def extract_resume_text():
    if not os.path.exists(RESUME_PATH):
        print(f"Error: Resume not found at {RESUME_PATH}")
        return

    try:
        reader = PdfReader(RESUME_PATH)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
        
        context = {
            "file_name": os.path.basename(RESUME_PATH),
            "full_text": full_text.strip(),
            "last_extracted": os.path.getmtime(RESUME_PATH)
        }
        
        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            json.dump(context, f, indent=4)
        
        print(f"SUCCESS: Resume context extracted and saved to {OUTPUT_PATH}")
    except Exception as e:
        print(f"Error extracting resume: {e}")

if __name__ == "__main__":
    extract_resume_text()
