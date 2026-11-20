@echo off
rem Run one digest pass.
rem Optional first argument: absolute path to python.exe
rem NOTE: keep this file ASCII-only - cmd.exe reads .bat in the local ANSI codepage,
rem       so Chinese comments would be garbled and may break parsing.
cd /d "%~dp0.."
if not exist "data\logs" mkdir "data\logs"

set "PY=%~1"
if "%PY%"=="" (
    if exist ".venv\Scripts\python.exe" (
        set "PY=.venv\Scripts\python.exe"
    ) else (
        set "PY=python"
    )
)

rem Do not use %date% here: it is locale-encoded in cmd and breaks when read as UTF-8.
rem Python's own log lines already carry timestamps.
echo ==== run start ==== >> "data\logs\daily.log"
"%PY%" -m aidaily >> "data\logs\daily.log" 2>&1
echo ==== run exit=%ERRORLEVEL% ==== >> "data\logs\daily.log"
