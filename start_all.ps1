# PowerShell script to start all servers for RollCall FRS

# Start API server (Python, venv activated)
Start-Process powershell -ArgumentList '-NoExit', '-Command', '.\.venv\Scripts\Activate; python lecturer_api.py' -WorkingDirectory $PWD

# Start React/Vite frontend (npm run dev)
Start-Process powershell -ArgumentList '-NoExit', '-Command', 'cd academe-view-suite; npm run dev' -WorkingDirectory $PWD

# (Optional) Start Admin Panel API server
# Start-Process powershell -ArgumentList '-NoExit', '-Command', '.\.venv\Scripts\Activate; python admin_api.py' -WorkingDirectory $PWD
