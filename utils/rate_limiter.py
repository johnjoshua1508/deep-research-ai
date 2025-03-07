import time
import logging
from typing import Dict, Any, List
from config import GROQ_MODELS, RATE_LIMITS

logger = logging.getLogger(__name__)

class RateLimiter:
    """Rate limiter for API calls"""
    
    def __init__(self):
        """Initialize the rate limiter"""
        self.models = list(GROQ_MODELS.keys())
        self.rate_limits = RATE_LIMITS
        self.last_request_time = {}
        self.request_counts = {}
        self.token_counts = {}
        
        # Initialize counters for each model
        for model in self.models:
            self.last_request_time[model] = 0
            self.request_counts[model] = 0
            self.token_counts[model] = 0
    
    def get_available_model(self) -> str:
        """
        Get an available model that hasn't hit rate limits
        
        Returns:
            str: The model name
        """
        current_time = time.time()
        
        # Reset counters if a minute has passed
        for model in self.models:
            if current_time - self.last_request_time.get(model, 0) > 60:
                self.request_counts[model] = 0
                self.token_counts[model] = 0
                self.last_request_time[model] = current_time
        
        # Find a model that hasn't hit rate limits
        for model in self.models:
            if (self.request_counts.get(model, 0) < self.rate_limits[model]["requests_per_minute"] and
                self.token_counts.get(model, 0) < self.rate_limits[model]["tokens_per_minute"]):
                return model
        
        # If all models have hit rate limits, use the first one and log a warning
        logger.warning("All models have hit rate limits. Using the first model.")
        return self.models[0]
    
    def update_rate_limits(self, model: str, limit_type: str, count: int = 1) -> None:
        """
        Update rate limits for a model
        
        Args:
            model (str): The model name
            limit_type (str): The type of limit ('request' or 'tokens')
            count (int): The count to add
        """
        current_time = time.time()
        
        # Reset counters if a minute has passed
        if current_time - self.last_request_time.get(model, 0) > 60:
            self.request_counts[model] = 0
            self.token_counts[model] = 0
        
        # Update the last request time
        self.last_request_time[model] = current_time
        
        # Update the appropriate counter
        if limit_type == "request":
            self.request_counts[model] = self.request_counts.get(model, 0) + 1
        elif limit_type == "tokens":
            self.token_counts[model] = self.token_counts.get(model, 0) + count

    def reset_usage_stats(self):
        """Reset usage statistics"""
        for model in self.models:
            self.request_counts[model] = 0
            self.token_counts[model] = 0

