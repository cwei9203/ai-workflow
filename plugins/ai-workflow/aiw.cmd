@echo off
rem ai-development-workflow:managed
setlocal
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
pushd "%~dp0" >nul
python -c "import sys" >nul 2>nul
if errorlevel 1 goto use_py
python -m ai_workflow %*
set "AIW_EXIT=%ERRORLEVEL%"
goto finish
:use_py
py -3 -m ai_workflow %*
set "AIW_EXIT=%ERRORLEVEL%"
:finish
popd >nul
exit /b %AIW_EXIT%
