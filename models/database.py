from pymongo import MongoClient
import chromadb
import logging
from config import MONGO_URI

logger = logging.getLogger(__name__)

# Initialize MongoDB
mongo_client = MongoClient(MONGO_URI)
db = mongo_client['deep_research_db']
chats_collection = db['chats']
settings_collection = db['settings']

# Initialize ChromaDB
try:
    chroma_client = chromadb.Client()
    try:
        research_collection = chroma_client.get_collection(name="research_data")
        logger.info("Retrieved existing ChromaDB collection")
    except ValueError:  # Updated exception type for newer ChromaDB
        research_collection = chroma_client.create_collection(name="research_data")
        logger.info("Created new ChromaDB collection")
except Exception as e:
    logger.error(f"Error initializing ChromaDB: {str(e)}")
    research_collection = None

def get_chat(chat_id):
    """Get a chat by ID"""
    return chats_collection.find_one({"_id": chat_id})

def get_all_chats():
    """Get all chats sorted by creation date"""
    return list(chats_collection.find().sort('created_at', -1))

def create_chat(chat_id, query):
    """Create a new chat"""
    from datetime import datetime

    chat_data = {
        "_id": chat_id,
        "query": query,
        "created_at": datetime.now(),
        "status": "in_progress"
    }

    chats_collection.insert_one(chat_data)
    return chat_data

def update_chat(chat_id, update_data):
    """Update a chat with new data"""
    chats_collection.update_one(
        {"_id": chat_id},
        {"$set": update_data}
    )

def get_settings():
    """Get application settings"""
    from config import GROQ_MODELS, DEFAULT_MODEL

    settings = settings_collection.find_one({"type": "app_settings"})

    if not settings:
        # Create default settings
        default_settings = {
            "type": "app_settings",
            "selected_model": DEFAULT_MODEL,
            "available_models": list(GROQ_MODELS.keys())
        }
        settings_collection.insert_one(default_settings)
        settings = default_settings

    # Remove _id for JSON serialization
    if '_id' in settings:
        del settings['_id']

    return settings

def update_settings(new_settings):
    """Update application settings"""
    settings_collection.update_one(
        {"type": "app_settings"},
        {"$set": new_settings},
        upsert=True
    )
    return get_settings()

def store_research_data(documents, metadatas, ids):
    """Store research data in ChromaDB"""
    if research_collection:
        try:
            research_collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            return True
        except Exception as e:
            logger.error(f"Error storing research data: {str(e)}")
    return False

def query_research_data(query, n_results=5):
    """Query research data from ChromaDB"""
    if research_collection:
        try:
            results = research_collection.query(
                query_texts=[query],
                n_results=n_results
            )
            return results
        except Exception as e:
            logger.error(f"Error querying research data: {str(e)}")
    return None

