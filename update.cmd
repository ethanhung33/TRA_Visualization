@echo off
rem One-click update for all timetable routes. Real logic lives in update.ps1.
rem Usage:
rem   update.cmd                     update every route
rem   update.cmd -Only tra hsr       update only TRA and HSR
rem   update.cmd -ListRoutes         list all route keys
rem   update.cmd -IncludeTopology    also re-scrape topology (rarely needed)
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0update.ps1" %*
exit /b %ERRORLEVEL%
