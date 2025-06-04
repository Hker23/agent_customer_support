import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langgraph.graph import END, StateGraph
from langsmith import Client
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.callbacks.tracers import LangChainTracer
from typing import Dict, Any

from src.models.types import State, PurchaseInformation, UserIntent
from src.agents.agent_nodes import AgentNodes
from src.tools import lookup_tools
from src.utils.config import setup_langsmith
from src.database.db_manager import db_manager
from src.utils.graph_utils import create_traced_node

def setup_vectorstores():
    """Create vectorstore indexes for all artists, albums, and songs."""
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    return lookup_tools.setup_vectorstores(embeddings)

def init_models(tracer):
    """Initialize all LLM models with tracing."""
    # Initialize base models with callbacks
    info_base = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        callbacks=[tracer],
        max_retries=2,
        timeout=30  # 30 second timeout
    )
    qa_base = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        callbacks=[tracer],
        max_retries=2,
        timeout=30  # 30 second timeout
    )
    router_base = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        callbacks=[tracer],
        max_retries=2,
        timeout=30  # 30 second timeout
    )
    
    # Add structured output
    info_llm = info_base.with_structured_output(
        PurchaseInformation, 
        method="json_schema", 
        include_raw=True
    )
    
    qa_llm = qa_base
    
    # We'll let the AgentNodes class handle router LLM structured output
    router_llm = router_base

    return info_llm, qa_llm, router_llm

def build_graph(tracer: LangChainTracer) -> StateGraph:
    """Build the agent workflow graph."""
    # Initialize models and agent nodes
    info_llm, qa_llm, router_llm = init_models(tracer)
    agent_nodes = AgentNodes(info_llm, qa_llm, router_llm)

    # Define the state schema
    workflow = StateGraph(
        state_schema=State,
    )
    
    # Add nodes with tracing
    create_traced_node(workflow, "route", agent_nodes.route_request, tracer)
    create_traced_node(workflow, "gather_info", agent_nodes.gather_info, tracer)
    create_traced_node(workflow, "process_refund", agent_nodes.process_refund, tracer)
    create_traced_node(workflow, "process_lookup", agent_nodes.process_lookup, tracer)
    create_traced_node(workflow, "process_music_query", agent_nodes.process_music_query, tracer)
    create_traced_node(workflow, "default_response", agent_nodes.default_response, tracer)

    # Make the flow strictly sequential
    workflow.set_entry_point("route")
    
    # Route node conditional edges
    workflow.add_conditional_edges(
        "route",
        lambda x: x.get("next", "gather_info"),
        {
            "gather_info": "gather_info",
            "process_music_query": "process_music_query",
            "default_response": "default_response"
        }
    )
    
    # Gather info conditional edges
    workflow.add_conditional_edges(
        "gather_info",
        lambda x: x.get("next", "default_response"),
        {
            "process_refund": "process_refund",
            "process_lookup": "process_lookup",
            "default_response": "default_response"
        }
    )
    
    # Add edges for terminal nodes
    workflow.add_edge("process_refund", END)
    workflow.add_edge("process_lookup", END)
    workflow.add_edge("process_music_query", END)
    workflow.add_edge("default_response", END)

    # Compile the graph
    return workflow.compile()

__all__ = ["setup_vectorstores", "init_models", "build_graph"] 