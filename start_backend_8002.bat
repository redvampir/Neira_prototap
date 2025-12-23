@echo off
chcp 65001
echo Starting Neira Backend on port 8002...
python -c "import uvicorn; uvicorn.run('backend.api:app', host='0.0.0.0', port=8002, log_level='info')"
pause
