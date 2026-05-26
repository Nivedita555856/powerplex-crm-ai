@echo off
title PowerPlex — Health Check

echo.
echo  PowerPlex CRM AI — Health Check
echo  ════════════════════════════════
echo.

call venv\Scripts\activate.bat 2>nul

python -c "
import os, sys
from dotenv import load_dotenv
load_dotenv()

checks = []

# Python version
checks.append(('Python', f'{sys.version_info.major}.{sys.version_info.minor}', True))

# Core packages
pkgs = [('groq','LLM (Groq)'), ('fastapi','FastAPI'), ('uvicorn','Uvicorn'),
        ('pinecone','Pinecone RAG'), ('sentence_transformers','Embeddings'),
        ('networkx','Knowledge Graph'), ('httpx','HTTP Client')]
for mod, label in pkgs:
    try:
        __import__(mod)
        checks.append((label, 'installed', True))
    except ImportError:
        checks.append((label, 'MISSING — pip install ' + mod, False))

# .env credentials
creds = [
    ('GROQ_API_KEY',     'Groq LLM key'),
    ('PINECONE_API_KEY', 'Pinecone key'),
    ('SUPABASE_URL',     'Supabase URL'),
    ('N8N_WEBHOOK_URL',  'n8n ticket webhook'),
    ('BACKEND_PUBLIC_URL','ngrok/public URL'),
]
for key, label in creds:
    val = os.getenv(key, '')
    if val and 'YOUR-' not in val:
        masked = val[:12] + '...' if len(val) > 12 else val
        checks.append((label, masked, True))
    else:
        checks.append((label, 'NOT SET', False))

# Data files
import glob
csvs = glob.glob('data/*.csv')
checks.append(('Data files', f'{len(csvs)} CSV files found', len(csvs) > 0))

# Print results
ok = sum(1 for _,_,s in checks if s)
total = len(checks)
for label, val, status in checks:
    icon = '[OK]  ' if status else '[WARN]'
    print(f'  {icon} {label:<28} {val}')

print()
print(f'  {ok}/{total} checks passed')
if ok == total:
    print('  Everything looks good — run run.bat to start')
else:
    print('  Fix the warnings above, then run run.bat')
"

echo.
pause
