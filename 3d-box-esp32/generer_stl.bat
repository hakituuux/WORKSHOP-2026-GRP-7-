@echo off
cd /d "%~dp0"
echo Installation des dependances...
python -m pip install -r requirements.txt -q
echo.
python generate_stl.py
echo.
pause
