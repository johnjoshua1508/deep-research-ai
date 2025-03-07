import requests
import logging
import json
import os
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class TavilyClient:
    """Client for interacting with the Tavily API"""
    
    @staticmethod
    def search(query: str, search_depth: str = "advanced", max_results: int = 5) -> Dict[str, Any]:
        """
        Execute a search using the Tavily API
        
        Args:
            query (str): The search query
            search_depth (str): The depth of search ('basic' or 'advanced')
            max_results (int): Maximum number of results to return
            
        Returns:
            Dict[str, Any]: The search results
        """
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            logger.error("Tavily API key not found in environment variables")
            return {"error": "API key not found", "results": []}
        
        url = "https://api.tavily.com/search"
        
        # Ensure query is a string, not a dictionary
        if isinstance(query, dict):
            if 'query' in query:
                query = query['query']
            else:
                query = str(query)
        
        payload = {
            "api_key": api_key,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results
        }
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()  # Raise exception for 4XX/5XX responses
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error in Tavily search: {str(e)}")
            # Return empty results instead of raising an exception
            return {"error": str(e), "results": []}


class GroqClient:
    """Client for interacting with the Groq API"""
    
    @staticmethod
    def generate_text(
        model: str,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Generate text using the Groq API
        
        Args:
            model (str): The model to use
            prompt (str): The prompt to generate from
            system_prompt (str, optional): System prompt for the model
            temperature (float): Sampling temperature
            max_tokens (int): Maximum tokens to generate
            
        Returns:
            Dict[str, Any]: The API response
        """
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            logger.error("Groq API key not found in environment variables")
            return {"error": "API key not found"}
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error in Groq API call: {str(e)}")
            return {"error": str(e)}
    
    @staticmethod
    def extract_json_from_text(text: str) -> Any:
        """
        Extract JSON from text response
        
        Args:
            text (str): Text that may contain JSON
            
        Returns:
            Any: Parsed JSON or None if parsing fails
        """
        try:
            # Try to find JSON in the text
            start_idx = text.find('[')
            end_idx = text.rfind(']') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = text[start_idx:end_idx]
                return json.loads(json_str)
            
            # If not found, try to find JSON object
            start_idx = text.find('{')
            end_idx = text.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = text[start_idx:end_idx]
                return json.loads(json_str)
            
            # If still not found, try to parse the entire text
            return json.loads(text)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to extract JSON from text: {str(e)}")
            return None

