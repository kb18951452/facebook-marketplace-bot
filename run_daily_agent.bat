@echo off
cd /d C:\Users\kenne\gitrepo\facebook-marketplace-bot
C:\Users\kenne\AppData\Local\Programs\Python\Python310\python.exe schedule_gate.py >> bot_stdout.log 2>&1
if errorlevel 3 exit /b 0
C:\Users\kenne\AppData\Local\Programs\Python\Python310\python.exe run_session.py >> bot_stdout.log 2>&1
