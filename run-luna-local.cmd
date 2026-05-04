@echo off
setlocal

cd /d "%~dp0"

echo.
echo  LUNA — starting API ^(port 8000^) + web ^(port 5173^) in this window.
echo  Press Ctrl+C to stop both.
echo.

call npm.cmd install
if errorlevel 1 (
  echo npm install failed.
  pause
  exit /b 1
)

echo.
echo Installing / updating InnerVoice Jelly Python deps...
python -m pip install -r "%~dp0InnerVoice_Jelly\requirements.txt" -q
if errorlevel 1 (
  echo pip install failed. Is Python on PATH?
  pause
  exit /b 1
)

call npm.cmd run dev
if errorlevel 1 pause
