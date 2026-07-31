import sys, os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(ROOT_DIR, "NowCurry")

sys.path.insert(0, APP_DIR)
sys.path.insert(0, ROOT_DIR)

errors = []

# Test 1: utils
try:
    from utils import safe_get, format_salary, format_experience
    assert safe_get({'a': {'b': 1}}, 'a', 'b') == 1
    assert safe_get({'a': None}, 'a') is None
    assert format_salary({'min': 500000, 'max': 1500000}) == '5-15 LPA'
    print("[PASS] utils")
except Exception as e:
    errors.append(f"[FAIL] utils: {e}")

# Test 2: config_models
try:
    from config_models import AppConfig, CredentialsConfig
    c = CredentialsConfig(username='test@test.com', password='pass123')
    assert c.username == 'test@test.com'
    print("[PASS] config_models")
except Exception as e:
    errors.append(f"[FAIL] config_models: {e}")

# Test 3: stealth_factory
try:
    from stealth_factory import StealthFactory
    p  = StealthFactory.generate_profile()
    js = StealthFactory.get_stealth_scripts()
    opts = StealthFactory.get_selenium_options(p)
    assert len(js) > 500, f"JS only {len(js)} chars — stub not replaced!"
    assert len(opts) > 5
    print(f"[PASS] stealth_factory: city={p['city']} JS={len(js)}chars opts={len(opts)}")
except Exception as e:
    errors.append(f"[FAIL] stealth_factory: {e}")

# Test 4: job_matcher
try:
    from job_matcher import JobMatcher
    m = JobMatcher({'job_titles': ['Python Developer'], 'location': 'Bangalore'})
    match, score = m.match_job({'title': 'Senior Python Developer', 'jobLocation': 'Bangalore'})
    print(f"[PASS] job_matcher: match={match} score={score:.1f}%")
except Exception as e:
    errors.append(f"[FAIL] job_matcher: {e}")

# Test 5: application_handler
try:
    from application_handler import ApplicationHandler
    print("[PASS] application_handler")
except Exception as e:
    errors.append(f"[FAIL] application_handler: {e}")

# Test 6: naukri_client
try:
    from naukri_client import NaukriClient
    print("[PASS] naukri_client")
except Exception as e:
    errors.append(f"[FAIL] naukri_client: {e}")

# Test 7: AgenticRAG
try:
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    from RAG.AgenticRAG.agentic_rag_engine import AgenticRAG
    rag = AgenticRAG()
    qs  = rag.extract_questions("We need 3 years experience, notice period within 30 days, open to relocate to Bangalore.")
    print(f"[PASS] AgenticRAG: extracted {len(qs)} questions: {qs[:2]}")
except Exception as e:
    errors.append(f"[FAIL] AgenticRAG: {e}")

# Test 8: MultiRAG import
try:
    from RAG.MultiRAG.context_aggregator import MultiRAG
    print("[PASS] MultiRAG")
except Exception as e:
    errors.append(f"[FAIL] MultiRAG: {e}")

# Summary
print()
print("=" * 50)
if errors:
    print(f"RESULT: {len(errors)} FAILURE(S)")
    for err in errors:
        print(err)
    sys.exit(1)
else:
    print("RESULT: ALL TESTS PASSED")
