# backend/run.py
"""
PyInstaller entry point.
Runs the FastAPI backend as a subprocess-friendly uvicorn server.
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="warning")
