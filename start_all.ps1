# PowerShell script to start all servers for RollCall FRS

# Start API server (Python, venv activated)

# Start React/Vite frontend (npm run dev)

# (Optional) Start Admin Panel API server

# Activate the virtual environment, then run main.py and lec_main.py in new windows

# Start main.py in a new PowerShell window with venv activated
Start-Process powershell -ArgumentList '-NoExit', '-Command', '. .\.venv\Scripts\Activate.ps1; python main.py'

# Start lec_main.py in a new PowerShell window with venv activated
Start-Process powershell -ArgumentList '-NoExit', '-Command', '. .\.venv\Scripts\Activate.ps1; python lec_main.py'
