"""Configuration settings for the application."""
import os
from langsmith import Client

def setup_langsmith():
    """Setup LangSmith configuration."""
    # These environment variables need to be set for LangSmith tracing
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = "music-store-support"
    
    # Initialize LangSmith client
    return Client() 