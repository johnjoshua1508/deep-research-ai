from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import os
import uuid
import threading
import logging
import json
from datetime import datetime

# Import configuration
from config import SECRET_KEY

# Import database models
from models.database import (
    get_chat, 
    get_all_chats, 
    create_chat, 
    update_chat, 
    get_settings, 
    update_settings
)

# Import agents
from agents.research_agent import ResearchAgent
from agents.drafting_agent import DraftingAgent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Reduce logging verbosity
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS
app.config['SECRET_KEY'] = SECRET_KEY

# Active research agents and threads
active_agents = {}
active_threads = {}
research_status = {}

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chats', methods=['GET'])
def get_chats():
    chats = get_all_chats()
    
    # Convert ObjectId to string for JSON serialization
    for chat in chats:
        chat['_id'] = str(chat['_id'])
    
    return jsonify(chats)

@app.route('/api/chat/<chat_id>', methods=['GET'])
def get_chat_by_id(chat_id):
    chat = get_chat(chat_id)
    
    if not chat:
        return jsonify({"error": "Chat not found"}), 404
    
    # Convert ObjectId to string for JSON serialization
    chat['_id'] = str(chat['_id'])
    
    return jsonify(chat)

@app.route('/api/settings', methods=['GET'])
def get_app_settings():
    settings = get_settings()
    return jsonify(settings)

@app.route('/api/settings', methods=['POST'])
def update_app_settings():
    new_settings = request.json
    
    # Validate model selection
    from config import GROQ_MODELS
    if 'selected_model' in new_settings and new_settings['selected_model'] not in GROQ_MODELS:
        return jsonify({"error": "Invalid model selection"}), 400
    
    # Update settings
    updated_settings = update_settings(new_settings)
    return jsonify(updated_settings)

@app.route('/api/research/start', methods=['POST'])
def start_research():
    data = request.json
    query = data.get('query')
    
    if not query:
        return jsonify({"error": "No query provided"}), 400
    
    # Create a new chat
    chat_id = str(uuid.uuid4())
    
    # Save to MongoDB
    create_chat(chat_id, query)
    
    # Initialize status
    research_status[chat_id] = {
        "progress": 5,
        "message": "Starting research...",
        "search_queries": [],
        "references": [],
        "analysis": None,
        "completed": False
    }
    
    # Create research agent with custom callback
    def status_callback(progress, message, search_queries=None, references=None, analysis=None):
        if chat_id in research_status:
            research_status[chat_id]["progress"] = progress
            research_status[chat_id]["message"] = message
            if search_queries:
                research_status[chat_id]["search_queries"] = search_queries
            if references:
                research_status[chat_id]["references"] = references
            if analysis:
                research_status[chat_id]["analysis"] = analysis
                research_status[chat_id]["completed"] = True
                # Update the chat in the database with the completed status
                update_chat(chat_id, {
                    "status": "completed",
                    "completed_at": datetime.now()
                })
    
    research_agent = ResearchAgent(query, chat_id, status_callback=status_callback)
    active_agents[chat_id] = research_agent
    
    # Start research in a separate thread
    def research_workflow():
        try:
            # Start the research process
            research_agent.start_research()
            
            # Clean up
            if chat_id in active_agents:
                del active_agents[chat_id]
            if chat_id in active_threads:
                del active_threads[chat_id]
        
        except Exception as e:
            logger.error(f"Error in research workflow: {str(e)}")
            if chat_id in research_status:
                research_status[chat_id]["error"] = str(e)
                research_status[chat_id]["message"] = f"Research failed: {str(e)}"
                research_status[chat_id]["progress"] = 0
            
            # Clean up on error
            if chat_id in active_agents:
                del active_agents[chat_id]
            if chat_id in active_threads:
                del active_threads[chat_id]
    
    # Start the research thread
    research_thread = threading.Thread(target=research_workflow)
    research_thread.daemon = True
    research_thread.start()
    
    # Store the thread
    active_threads[chat_id] = research_thread
    
    return jsonify({"chat_id": chat_id, "query": query})

@app.route('/api/research/status/<chat_id>', methods=['GET'])
def get_research_status(chat_id):
    # If chat is in active research, return status
    if chat_id in research_status:
        return jsonify(research_status[chat_id])
    
    # Otherwise, get chat from database
    chat = get_chat(chat_id)
    if not chat:
        return jsonify({"error": "Chat not found"}), 404
    
    # Convert ObjectId to string for JSON serialization
    chat_id = str(chat['_id'])
    
    # Return completed status
    if chat.get('status') == 'completed':
        return jsonify({
            "progress": 100,
            "message": "Research completed",
            "search_queries": chat.get('search_queries', []),
            "references": chat.get('references', []),
            "analysis": chat.get('analysis', ''),
            "completed": True
        })
    
    # Return in-progress status
    return jsonify({
        "progress": 50,
        "message": "Research in progress...",
        "search_queries": chat.get('search_queries', []),
        "references": chat.get('references', []),
        "completed": False
    })

@app.route('/api/research/stop/<chat_id>', methods=['POST'])
def stop_research(chat_id):
    if chat_id in active_agents:
        # Stop the research agent
        active_agents[chat_id].stop_research()
        del active_agents[chat_id]
        
        # Update chat status
        update_chat(chat_id, {
            "status": "stopped",
            "completed_at": datetime.now()
        })
        
        # Remove thread reference
        if chat_id in active_threads:
            del active_threads[chat_id]
        
        # Update status
        if chat_id in research_status:
            research_status[chat_id]["progress"] = 0
            research_status[chat_id]["message"] = "Research stopped"
        
        return jsonify({"status": "stopped"})
    else:
        return jsonify({"error": "No active research found for this chat"}), 404

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"})

@app.route('/debug', methods=['GET'])
def debug():
    """Debug endpoint to check if server is responding"""
    return jsonify({
        "status": "ok",
        "message": "Server is responding correctly",
        "active_agents": list(active_agents.keys()),
        "active_threads": list(active_threads.keys()),
        "research_status": {k: v["progress"] for k, v in research_status.items()} if research_status else {}
    })

if __name__ == '__main__':
    # Use standard Flask server
    port = 5000
    host = '0.0.0.0'
    print(f"\n* Running on http://127.0.0.1:{port}/ (Press CTRL+C to quit)")
    print(f"* Also accessible at http://{host}:{port}/")
    app.run(debug=True, host=host, port=port)

