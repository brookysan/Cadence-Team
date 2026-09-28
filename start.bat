@echo off
echo Starting Cadence Team...
echo.

echo Checking dependencies (installs anything missing, then continues)...
python -m pip install --quiet -r "%~dp0backend\requirements.txt"
python -m pip install --quiet -r "%~dp0frontend\requirements.txt"

echo.
echo Checking Microsoft sign-in...
pushd "%~dp0backend"
python setup_auth.py
popd

echo.
start "Cadence Team Backend"  cmd /k "cd /d "%~dp0backend"  && python -m uvicorn app.main:app --port 8010"
start "Cadence Team Frontend" cmd /k "cd /d "%~dp0frontend" && python -m streamlit run streamlit_app.py --server.port 8511 --server.address 127.0.0.1 --server.headless true"
echo.
echo Two windows just opened - one for the backend, one for the frontend.
echo Leave them open while you use Cadence Team; closing a window stops that part.
echo.
echo Waiting a few seconds for them to start, then opening your browser...
ping -n 7 127.0.0.1 >nul
start http://localhost:8511
echo.
echo If the page shows a connection error, just refresh it after a moment -
echo the servers may still be finishing startup.
