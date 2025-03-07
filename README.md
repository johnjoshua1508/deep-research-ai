# Deep Research AI Architecture

## System Overview

The Deep Research AI system is designed as a dual-agent architecture that leverages LangGraph for workflow management and external APIs for information gathering and analysis.

## Components

### 1. Research Agent

The Research Agent is responsible for:
- Generating search queries based on the user's research topic
- Executing searches using the Tavily API
- Processing and storing search results
- Managing the research workflow

### 2. Drafting Agent

The Drafting Agent is responsible for:
- Analyzing the gathered information
- Generating a comprehensive analysis
- Adding proper citations to references
- Structuring the content for readability

### 3. Database Layer

- **MongoDB**: Stores chat history, user queries, and application settings
- **ChromaDB**: Vector database for storing and retrieving research data

### 4. API Clients

- **Tavily Client**: Handles communication with the Tavily search API
- **Groq Client**: Manages interactions with the Groq LLM API

### 5. Web Interface

- **Flask Backend**: Handles API routes and server-side logic
- **Frontend**: Modern UI with real-time progress updates

## Workflow

1. User submits a research query
2. Research Agent generates search queries
3. Research Agent executes searches via Tavily API
4. Results are stored in MongoDB and ChromaDB
5. Drafting Agent analyzes the gathered information
6. Drafting Agent generates a comprehensive analysis
7. Results are presented to the user with citations

## Technologies

- **Python**: Primary programming language
- **Flask**: Web framework
- **LangGraph**: Workflow management
- **LangChain**: LLM integration
- **MongoDB**: Document database
- **ChromaDB**: Vector database
- **Tavily API**: Web search
- **Groq API**: Large language models

## Installation

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - Unix/MacOS: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and add your API keys
6. Run the application: `python app.py`

## Usage

1. Open your browser and navigate to `http://localhost:5000`
2. Enter a research query in the input field
3. View real-time research progress
4. Read the generated analysis with citations

## Configuration

You can configure the following settings in the `.env` file:
- API keys for Tavily and Groq
- MongoDB connection URI
- Flask secret key
