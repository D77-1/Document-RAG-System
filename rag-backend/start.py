import uvicorn
import os
import sys

# Ensure the script's directory is the working directory so that
# relative paths (data/, config/, .env) resolve correctly.
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_BASE_DIR)
sys.path.insert(0, _BASE_DIR)

if __name__ == "__main__":
    # Use 0.0.0.0 to be accessible from all interfaces
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
