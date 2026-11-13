@echo off
rem Mo Graylog tren Windows. Can Python 3.9+ (https://www.python.org/downloads/ hoac: winget install Python.Python.3.12)
where pyw >nul 2>nul && (start "" pyw -3 "%~dp0gl-ui.py" - browser & exit /b)
where pythonw >nul 2>nul && (start "" pythonw "%~dp0gl-ui.py" - browser & exit /b)
echo Chua cai Python. Cai Python 3 roi chay lai file nay.
pause
