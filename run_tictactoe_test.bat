@echo off
echo Starting backend...
start /MIN python -m backend.api
timeout /t 8 /nobreak >nul
echo Backend started!
echo.
echo Running test...
python test_neira_tictactoe.py
