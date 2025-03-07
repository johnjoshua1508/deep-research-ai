import logging
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from utils.api_clients import GroqClient
from utils.rate_limiter import RateLimiter
from models.database import update_chat
from config import MIN_WORDS

logger = logging.getLogger(__name__)

# Initialize rate limiter
rate_limiter = RateLimiter()

class DraftingAgent:
    """Agent for drafting the final analysis based on research results"""
    
    def __init__(self, chat_id: str, status_callback: Callable = None):
        """
        Initialize the drafting agent
        
        Args:
            chat_id (str): The chat ID
            status_callback: Callback function for status updates
                callback(progress: int, message: str, search_queries: Optional[List[str]], 
                        references: Optional[List[Dict]], analysis: Optional[str])
        """
        self.chat_id = chat_id
        self.status_callback = status_callback
    
    def generate_analysis(self, query: str, references: List[Dict[str, Any]]) -> str:
        """
        Generate an analysis based on the research results
        
        Args:
            query (str): The original research query
            references (List[Dict]): The references to use for analysis
        
        Returns:
            str: The generated analysis
        """
        if not references:
            logger.warning(f"No references provided for analysis in chat {self.chat_id}")
            
            # Create a fallback analysis when no references are available
            fallback_analysis = f"""
No Research Results Available

We were unable to retrieve research results for your query: "{query}"

This could be due to one of the following reasons:
1. API connection issues with our search provider
2. Missing or invalid API credentials
3. Search query formatting issues

Recommendations:
* Check that your Tavily API key is correctly set in your environment variables
* Verify that your internet connection is stable
* Try a different search query
* Check the application logs for specific error messages

You can try again with a new query or after resolving any API configuration issues.
"""
            
            # Save the fallback analysis to MongoDB
            update_chat(
                self.chat_id,
                {
                    "analysis": fallback_analysis,
                    "completed_at": datetime.now(),
                    "status": "completed"
                }
            )
            
            # Emit the fallback analysis through the callback
            if self.status_callback:
                self.status_callback(100, "Research completed with no results", None, None, fallback_analysis)
            
            return fallback_analysis

        try:
            # Create a prompt template with cleaner formatting and stronger emphasis on length
            prompt_template = ChatPromptTemplate.from_template("""
Based on the following research results, create a comprehensive analysis on the topic:

Topic: {query}

Research Results:
{reference_content}

CRITICAL REQUIREMENTS:
1. LENGTH: Your analysis MUST be AT LEAST 2000 words. This is a STRICT requirement.
2. CITATIONS: You have {ref_count} references available. ONLY cite references that exist (1 to {ref_count}).
3. FORMAT: Use inline citations in the format (n) where n is the reference number.
4. SECTIONS: Each section must be separated by two newlines for proper formatting.

Structure your analysis with these sections:
Introduction
- Minimum 250 words
- Cite 2-3 references
- Provide context and overview

Current State and Challenges
- Minimum 400 words
- Cite 4-5 references
- Detail current landscape and obstacles

Key Technologies and Methods
- Minimum 400 words
- Cite 6-7 references
- Technical deep dive

Implementation and Best Practices
- Minimum 400 words
- Cite 4-5 references
- Practical guidelines

Economic and Security Impact
- Minimum 300 words
- Cite 3-4 references
- Business and security analysis

Future Perspectives
- Minimum 150 words
- Cite 3-4 references
- Trends and predictions

Conclusion
- Minimum 100 words
- Summarize key findings
- No word count note needed

Writing Guidelines:
1. Do NOT include word count requirements in the output
2. Format section headers without asterisks
3. Be thorough and detailed in each section
4. Include specific examples, statistics, and data points
5. Make meaningful connections between different sources
6. Use clear topic sentences and smooth transitions
7. Maintain a professional and academic tone
8. Ensure even distribution of citations throughout the text

Remember:
- Your analysis MUST be AT LEAST {min_words} words
- You MUST cite ALL {ref_count} references
- Each section must meet its minimum word count
- Be specific and detailed in your analysis
- Do NOT include formatting instructions or word count notes in the output
""")
            
            # Get an available model
            model_name = rate_limiter.get_available_model()
            
            # Prepare reference content with better formatting
            reference_texts = []
            for i, ref in enumerate(references):
                content = ref.get('content', '').strip()
                if content:
                    reference_texts.append(f"({i+1}) {ref['title']}:\n{content[:1000]}...\n")

            reference_content = "\n".join(reference_texts)
            
            logger.info(f"Generating analysis for chat {self.chat_id} with {len(references)} references")
            
            # Use the GroqClient with increased max_tokens
            response = GroqClient.generate_text(
                model=model_name,
                prompt=prompt_template.format(
                    query=query,
                    reference_content=reference_content,
                    ref_count=len(references),
                    min_words=MIN_WORDS
                ),
                system_prompt="You are a research assistant helping with deep analysis. Your task is to write a COMPREHENSIVE analysis that is AT LEAST 2000 words long and cites ALL available references.",
                temperature=0.3,
                max_tokens=8000  # Increased to allow for longer responses
            )
            
            # Update rate limits
            rate_limiter.update_rate_limits(model_name, "request")
            if response and 'usage' in response and 'total_tokens' in response['usage']:
                rate_limiter.update_rate_limits(model_name, "tokens", response['usage']['total_tokens'])
            
            # Extract and validate analysis from response
            if response and 'choices' in response:
                analysis = response['choices'][0]['message']['content']
                
                if not analysis or len(analysis.strip()) < 100:
                    logger.error(f"Generated analysis is too short or empty for chat {self.chat_id}")
                    return "Error: Generated analysis is too short or empty. Please try again."
                
                # Save the analysis to MongoDB
                update_chat(
                    self.chat_id,
                    {
                        "analysis": analysis,
                        "completed_at": datetime.now(),
                        "status": "completed"
                    }
                )
                
                logger.info(f"Successfully generated analysis for chat {self.chat_id}")
                
                # Emit the final analysis through the callback
                if self.status_callback:
                    self.status_callback(100, "Research completed", None, None, analysis)
                
                return analysis
            else:
                error_msg = "Failed to generate analysis - no valid response from model"
                logger.error(f"{error_msg} for chat {self.chat_id}")
                return error_msg
                
        except Exception as e:
            error_msg = f"Error analyzing results: {str(e)}"
            logger.error(f"{error_msg} for chat {self.chat_id}")
            return error_msg

