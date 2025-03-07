import logging
import uuid
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, TypedDict, Annotated, Callable
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph
from langgraph.constants import END
from utils.api_clients import TavilyClient, GroqClient
from utils.rate_limiter import RateLimiter
from models.database import store_research_data, update_chat
from agents.drafting_agent import DraftingAgent

logger = logging.getLogger(__name__)

# Initialize rate limiter
rate_limiter = RateLimiter()

# Define state type for type checking
class ResearchState(TypedDict):
    query: str
    search_queries: List[str]
    references: List[Dict[str, Any]]
    research_data: List[Any]
    progress: int
    error: Optional[str]

class ResearchAgent:
    """Research agent using LangGraph for workflow management"""
    
    def __init__(self, query: str, chat_id: str, status_callback: Callable = None):
        """
        Initialize the research agent
        
        Args:
            query (str): The research query
            chat_id (str): The chat ID
            status_callback: Callback function for status updates
                callback(progress: int, message: str, search_queries: Optional[List[str]], 
                        references: Optional[List[Dict]], analysis: Optional[str])
        """
        self.query = query
        self.chat_id = chat_id
        self.status_callback = status_callback
        self.search_queries = []
        self.progress = 0
        self.references = []
        self.research_data = []
        self.is_researching = False
        self._stop_requested = False
        
        # Create the research workflow
        self.workflow = self._create_workflow()
    
    def start_research(self):
        """Start the research process"""
        self.is_researching = True
        self._stop_requested = False
        self.progress = 5
        self._update_progress("Starting research process...")
        
        # Initial state
        initial_state: ResearchState = {
            "query": self.query,
            "search_queries": [],
            "references": [],
            "research_data": [],
            "progress": 5,
            "error": None
        }
        
        # Execute the workflow
        try:
            for event in self.workflow.stream(initial_state):
                # Check if stop was requested
                if self._stop_requested:
                    self.is_researching = False
                    self._update_progress("Research stopped")
                    return
            
                # Check if this is a state event
                if isinstance(event, tuple) and len(event) == 2:
                    event_type, state = event
                    # Only process state events
                    if event_type != "state":
                        continue
                else:
                    # Handle the case where event is just the state
                    state = event
            
                # Update agent state from workflow state
                if "search_queries" in state and state["search_queries"]:
                    self.search_queries = state["search_queries"]
                    self._emit_search_queries()
            
                if "references" in state and state["references"]:
                    self.references = state["references"]
            
                if "research_data" in state and state["research_data"]:
                    self.research_data = state["research_data"]
            
                if "progress" in state and state["progress"] != self.progress:
                    self.progress = state["progress"]
                    self._update_progress(f"Research progress: {self.progress}%")
            
                if "error" in state and state["error"]:
                    self._update_progress(f"Error: {state['error']}")
                    return
            
            # After workflow completes successfully
            if not self._stop_requested:
                self.is_researching = False
                
        except Exception as e:
            logger.error(f"Error in research workflow: {str(e)}")
            self._update_progress(f"Research failed: {str(e)}")
            self.is_researching = False
    
    def stop_research(self):
        """Stop the research process"""
        self._stop_requested = True
        self.is_researching = False
        self._update_progress("Stopping research...")

    def _create_workflow(self) -> StateGraph:
        """Create the research workflow using LangGraph"""
        # Define the workflow with typed state
        workflow = StateGraph(ResearchState)
        
        # Add nodes to the workflow
        workflow.add_node("generate_queries", self._generate_search_queries)
        workflow.add_node("execute_searches", self._execute_searches)
        workflow.add_node("process_results", self._process_results)
        
        # Define conditional routing based on error state
        def should_continue(state: ResearchState) -> str:
            return "continue" if state.get("error") is None else "error"
        
        # Add conditional edges for error handling
        workflow.add_conditional_edges(
            "generate_queries",
            should_continue,
            {
                "continue": "execute_searches",
                "error": END
            }
        )
        
        workflow.add_conditional_edges(
            "execute_searches",
            should_continue,
            {
                "continue": "process_results",
                "error": END
            }
        )
        
        workflow.add_edge("process_results", END)
        
        # Set the entry point
        workflow.set_entry_point("generate_queries")
        
        # Compile the workflow
        return workflow.compile()
    
    def _generate_search_queries(self, state: ResearchState) -> ResearchState:
        """Generate search queries for the research topic"""
        self._update_progress("Generating search queries...")
        
        # Get an available model
        model = rate_limiter.get_available_model()
        
        prompt = f"""
        Generate 5 specific search queries to thoroughly research the following topic:
        
        {state['query']}
        
        Format the queries as a JSON array of strings.
        """
        
        try:
            # Call Groq API
            response = GroqClient.generate_text(
                model=model,
                prompt=prompt,
                system_prompt="You are a research assistant helping with deep analysis.",
                temperature=0.3
            )
            
            # Update rate limits
            rate_limiter.update_rate_limits(model, "request")
            if response and 'usage' in response and 'total_tokens' in response['usage']:
                rate_limiter.update_rate_limits(model, "tokens", response['usage']['total_tokens'])
            
            # Extract queries from response
            if response and 'choices' in response:
                content = response['choices'][0]['message']['content']
                queries = GroqClient.extract_json_from_text(content)
                
                if queries and isinstance(queries, list):
                    state["search_queries"] = queries
                    state["progress"] = 20
                else:
                    # Fallback if JSON extraction failed
                    state["search_queries"] = [state["query"]]
                    state["progress"] = 15
            else:
                # Fallback if API call failed
                state["search_queries"] = [state["query"]]
                state["progress"] = 10
                state["error"] = "Failed to generate search queries"
        
        except Exception as e:
            logger.error(f"Error generating search queries: {str(e)}")
            state["search_queries"] = [state["query"]]
            state["progress"] = 10
            state["error"] = f"Error generating queries: {str(e)}"
        
        return state
    
    def _execute_searches(self, state: ResearchState) -> ResearchState:
        """Execute searches using the generated queries"""
        self._update_progress("Executing searches...")
    
        all_results = []
        references = []
        total_queries = len(state["search_queries"])
        search_failures = 0
    
        for i, query in enumerate(state["search_queries"]):
            self._update_progress(f"Searching for: {query}")
        
            try:
                # Call Tavily API
                search_results = TavilyClient.search(query)
            
                if search_results and 'results' in search_results and search_results['results']:
                    all_results.extend(search_results['results'])
                
                    # Store references
                    for result in search_results['results']:
                        reference = {
                            'title': result.get('title', 'No Title'),
                            'url': result.get('url', '#'),
                            'content': result.get('content', ''),
                            'score': result.get('score', 0)
                        }
                    
                        # Check if reference already exists
                        if not any(ref['url'] == reference['url'] for ref in references):
                            references.append(reference)
                elif 'error' in search_results:
                    logger.warning(f"Search error for query '{query}': {search_results.get('error')}")
                    search_failures += 1
        
                # Update progress
                progress_increment = 50 / total_queries
                state["progress"] = min(20 + int((i + 1) * progress_increment), 70)
                self._update_progress(f"Completed search {i+1}/{total_queries}")
            
            except Exception as e:
                logger.error(f"Error executing search for query '{query}': {str(e)}")
                self._update_progress(f"Error in search: {str(e)}")
                search_failures += 1
    
        # Check if all searches failed
        if search_failures == total_queries:
            state["error"] = "All search queries failed. Please check your Tavily API key and try again."
            return state
    
        # Store research data in ChromaDB
        if all_results:
            texts = [r.get('content', '') for r in all_results]
            metadatas = [{'title': r.get('title', ''), 'url': r.get('url', '')} for r in all_results]
            ids = [str(uuid.uuid4()) for _ in range(len(all_results))]
        
            store_research_data(texts, metadatas, ids)
    
        state["research_data"] = all_results
        state["references"] = references
        state["progress"] = 70
    
        return state
    
    def _process_results(self, state: ResearchState) -> ResearchState:
        """Process the search results"""
        self._update_progress("Processing search results...")
        
        # Update the chat with references and search queries
        update_chat(self.chat_id, {
            "references": state["references"],
            "search_queries": state["search_queries"],
            "research_data": state["research_data"]
        })
        
        # Store the references in the agent for the drafting agent
        self.references = state["references"]
        self.research_data = state["research_data"]
        
        # Create and run drafting agent with status callback
        def drafting_callback(progress, message, search_queries=None, references=None, analysis=None):
            if self.status_callback:
                self.status_callback(progress, message, search_queries, references, analysis)
        
        drafting_agent = DraftingAgent(self.chat_id, status_callback=drafting_callback)
        analysis = drafting_agent.generate_analysis(state["query"], state["references"])
        
        if analysis:
            # Update progress after analysis is complete
            state["progress"] = 100
            self._update_progress("Research completed", analysis=analysis)
        else:
            state["error"] = "Failed to generate analysis"
        
        return state
    
    def _update_progress(self, message: str, analysis: str = None):
        """Update and emit progress"""
        if self.status_callback:
            self.status_callback(
                self.progress, 
                message, 
                self.search_queries, 
                self.references,
                analysis
            )
        logger.info(f"Research progress [{self.chat_id}]: {self.progress}% - {message}")
    
    def _emit_search_queries(self):
        """Emit search queries"""
        if self.status_callback:
            self.status_callback(self.progress, "Generated search queries", self.search_queries)

