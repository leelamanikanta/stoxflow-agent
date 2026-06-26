import subprocess
import sys
import time
import os

processes = []
logs_dir = "logs"
os.makedirs(logs_dir, exist_ok=True)

phoenix_log_path = os.path.join(logs_dir, "phoenix.log")
backend_log_path = os.path.join(logs_dir, "backend.log")

try:
    print("\n" + "="*50)
    print("📈 STOXFLOW STACK LAUNCHER")
    print("="*50 + "\n")

    # Open log files
    phoenix_log = open(phoenix_log_path, "w", encoding="utf-8")
    backend_log = open(backend_log_path, "w", encoding="utf-8")

    # 1. Start Arize Phoenix Observability Server
    print("🚀 Starting Arize Phoenix Observability Server...")
    phoenix_proc = subprocess.Popen(
        [sys.executable, "-m", "phoenix.server.main", "serve"],
        stdout=phoenix_log,
        stderr=phoenix_log
    )
    processes.append(phoenix_proc)
    time.sleep(3)  # Allow Phoenix server to begin booting

    # 2. Start FastAPI Backend API Server
    print("🚀 Starting FastAPI Backend API Server (Uvicorn)...")
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=backend_log,
        stderr=backend_log
    )
    processes.append(backend_proc)
    time.sleep(2)

    # Check if they crashed immediately
    if phoenix_proc.poll() is not None:
        print("⚠️ Warning: Phoenix server failed to start or exited immediately. Check logs/phoenix.log")
    if backend_proc.poll() is not None:
        print("⚠️ Warning: FastAPI backend server failed to start or exited immediately. Check logs/backend.log")

    # 3. Start NiceGUI Frontend Dashboard
    print("🚀 Starting NiceGUI Frontend Dashboard...")
    frontend_proc = subprocess.Popen([sys.executable, "frontend/frontend.py"])
    processes.append(frontend_proc)

    print("\n⚡ Stack initialization completed!")
    print("👉 NiceGUI Frontend Dashboard:  http://localhost:8080")
    print("👉 FastAPI Backend API:         http://127.0.0.1:8000")
    print("👉 Phoenix Observability Panel: http://localhost:6006  (or http://localhost:4000)")
    print("\n[Press Ctrl+C inside this terminal to stop all 3 services]\n")
    
    # Block and wait for frontend process to exit or keyboard interrupt
    frontend_proc.wait()

except KeyboardInterrupt:
    print("\n🛑 Keyboard interrupt detected. Stopping all services...")
except Exception as e:
    print(f"\n❌ Error during execution: {e}")
finally:
    print("🧹 Cleaning up background processes...")
    for p in processes:
        try:
            p.terminate()
            p.wait(timeout=3)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
    print("✅ All services stopped successfully.")
