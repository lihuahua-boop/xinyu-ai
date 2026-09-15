@echo off
cd /d %~dp0
if not exist data mkdir data
set PYTHON_EXE=D:\biyesheji\python37\python.exe
if not exist "%PYTHON_EXE%" set PYTHON_EXE=python
echo 心屿 AI 启动中...
"%PYTHON_EXE%" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
pause
