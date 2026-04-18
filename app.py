from flask import Flask, render_template, request, jsonify
import threading
import queue
from Duolingo_Agent import DuolingoAgent

app = Flask(__name__)

# Global state
agent = None
log_queue = queue.Queue()

class WebAgent(DuolingoAgent):
    def log(self, message):
        log_queue.put(message)
        print(f"[WebAgent] {message}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_bot():
    global agent
    data = request.json
    api_key = data.get('api_key')
    browser_path = data.get('browser_path')
    
    if not agent:
        try:
            agent = WebAgent(api_key=api_key, browser_path=browser_path)
            # Save to config
            agent.config['api_key'] = api_key
            if browser_path:
                agent.config['browser_path'] = browser_path
            agent.save_config()
            
            # Run in a separate thread
            thread = threading.Thread(target=run_bot_logic)
            thread.daemon = True
            thread.start()
            return jsonify({"status": "success", "message": "Bot started in background."})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
    return jsonify({"status": "error", "message": "Bot already running."})

def run_bot_logic():
    global agent
    try:
        agent.wait_for_login()
        agent.start_lesson()
        agent.run_automation()
    except Exception as e:
        agent.log(f"Critical Error: {e}")

@app.route('/logs')
def get_logs():
    logs = []
    while not log_queue.empty():
        logs.append(log_queue.get())
    return jsonify({"logs": logs})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
