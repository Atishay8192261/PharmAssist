import os
import sys
import json
from dotenv import load_dotenv

try:
    import google.generativeai as genai
except Exception as e:
    print("import_error:", e)
    sys.exit(1)

load_dotenv()
api_key = os.getenv('GOOGLE_API_KEY')
print('HAS_KEY' if bool(api_key) else 'NO_KEY')
if not api_key:
    sys.exit(0)

genai.configure(api_key=api_key)
print('genai version:', getattr(genai, '__version__', 'unknown'))

try:
    models = list(genai.list_models())
except Exception as e:
    print('list_models_error:', e)
    sys.exit(2)

print('models count:', len(models))
out = []
for m in models:
    name = getattr(m, 'name', '')
    methods = list(getattr(m, 'supported_generation_methods', []) or [])
    out.append({'name': name, 'methods': methods})

print(json.dumps(out, indent=2))
