import os
import sys
import json
import yaml
import logging
import threading
import time
from flask import Flask, render_template, jsonify, request

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.main import main as run_bot_main, STOP_EVENT

app = Flask(__name__, template_folder='templates', static_folder='static')
logger = logging.getLogger("Chatbot.WebUI")

# Global thread reference
bot_thread = None

def read_env() -> dict:
    """Read key-value pairs from .env."""
    env_vars = {
        "GEMINI_API_KEY": "",
        "OPENAI_API_KEY": "",
        "DEEPSEEK_API_KEY": "",
        "XIAOMIMIMO_API_KEY": "",
        "XIAOMIMIMO_API_BASE": "https://token-plan-sgp.xiaomimimo.com/v1",
        "GPM_API_URL": "http://127.0.0.1:9495",
        "GPM_PROFILE_ID": "",
        "GPM_DEBUG_PORT": "9222"
    }
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    # Strip spaces and quotes
                    v = v.strip().strip('"').strip("'").strip()
                    env_vars[k] = v
    return env_vars

def write_env(new_vars: dict):
    """Write dictionary to .env, preserving comments and file structure."""
    lines = []
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            lines = f.readlines()
            
    output_lines = []
    keys_written = set()
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _ = stripped.split("=", 1)
            k = k.strip()
            if k in new_vars:
                # Format properly with quotes if it contains spaces or config values
                val = new_vars[k]
                output_lines.append(f"{k}={val}\n")
                keys_written.add(k)
            else:
                output_lines.append(line)
        else:
            output_lines.append(line)
            
    # Append any keys that weren't in the original file
    for k, v in new_vars.items():
        if k not in keys_written:
            output_lines.append(f"{k}={v}\n")
            
    with open(".env", "w", encoding="utf-8") as f:
        f.writelines(output_lines)

def load_settings() -> dict:
    config_path = os.path.join("config", "settings.yaml")
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def save_settings(data: dict):
    config_path = os.path.join("config", "settings.yaml")
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)

def load_whitelist() -> dict:
    whitelist_path = os.path.join("config", "whitelist.json")
    if not os.path.exists(whitelist_path):
        return {"allow_all": True, "allowed_threads": [], "allowed_names": []}
    with open(whitelist_path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {"allow_all": False, "allowed_threads": [], "allowed_names": []}

def save_whitelist(data: dict):
    whitelist_path = os.path.join("config", "whitelist.json")
    os.makedirs(os.path.dirname(whitelist_path), exist_ok=True)
    with open(whitelist_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_sent_messages() -> list:
    log_file = os.path.join("config", "sent_messages.json")
    if not os.path.exists(log_file):
        return []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def get_latest_logs(num_lines=100) -> str:
    log_file = "chatbot.log"
    if not os.path.exists(log_file):
        return "Log file empty or not created yet."
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return "".join(lines[-num_lines:])
    except Exception as e:
        return f"Error reading logs: {e}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status', methods=['GET'])
def get_status():
    global bot_thread
    is_running = bot_thread is not None and bot_thread.is_alive()
    return jsonify({
        "running": is_running,
        "logs": get_latest_logs(50)
    })

@app.route('/api/start', methods=['POST'])
def start_bot():
    global bot_thread
    is_running = bot_thread is not None and bot_thread.is_alive()
    if is_running:
        return jsonify({"success": False, "message": "Chatbot is already running."})
        
    logger.info("Starting chatbot background thread...")
    # Clear stop event
    STOP_EVENT.clear()
    
    # Reload environment variables for this process context
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    # Spawn thread
    bot_thread = threading.Thread(target=run_bot_main, daemon=True)
    bot_thread.start()
    
    # Wait a second to check if it started successfully
    time.sleep(1.5)
    
    return jsonify({
        "success": bot_thread.is_alive(),
        "message": "Chatbot thread started successfully." if bot_thread.is_alive() else "Chatbot failed to start. Check logs."
    })

@app.route('/api/stop', methods=['POST'])
def stop_bot():
    global bot_thread
    is_running = bot_thread is not None and bot_thread.is_alive()
    if not is_running:
        return jsonify({"success": False, "message": "Chatbot is not running."})
        
    logger.info("Signaling chatbot background thread to stop...")
    STOP_EVENT.set()
    
    # Wait up to 5 seconds for it to stop
    for _ in range(5):
        if not bot_thread.is_alive():
            break
        time.sleep(1.0)
        
    still_alive = bot_thread.is_alive()
    return jsonify({
        "success": not still_alive,
        "message": "Chatbot stopped successfully." if not still_alive else "Stop signal sent, but thread is still cleaning up."
    })

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'GET':
        env = read_env()
        settings = load_settings()
        return jsonify({
            "env": env,
            "settings": settings
        })
    else:
        # POST
        data = request.json
        if not data:
            return jsonify({"success": False, "message": "Invalid request payload."}), 400
            
        env_updates = data.get("env", {})
        settings_updates = data.get("settings", {})
        
        # Save .env
        env = read_env()
        env.update(env_updates)
        write_env(env)
        
        # Save settings.yaml
        settings = load_settings()
        settings.update(settings_updates)
        save_settings(settings)
        
        # Apply environment overrides to process dynamically
        for k, v in env_updates.items():
            os.environ[k] = str(v)
            
        return jsonify({"success": True, "message": "Configuration saved successfully."})

@app.route('/api/whitelist', methods=['GET', 'POST'])
def handle_whitelist():
    if request.method == 'GET':
        return jsonify(load_whitelist())
    else:
        data = request.json
        if not data:
            return jsonify({"success": False, "message": "Invalid payload."}), 400
        save_whitelist(data)
        return jsonify({"success": True, "message": "Whitelist updated successfully."})

@app.route('/api/messages', methods=['GET'])
def get_messages():
    return jsonify({"messages": get_sent_messages()})

if __name__ == '__main__':
    # Start web server on port 5000
    print("====================================================")
    print("  GPM Chatbot Control Panel starting at http://127.0.0.1:5000")
    print("====================================================")
    app.run(host='127.0.0.1', port=5000, debug=False)
