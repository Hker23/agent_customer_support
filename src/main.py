import os
from typing import List, TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.callbacks.tracers import LangChainTracer
from langgraph.graph import StateGraph, END
from src.agents.agent_nodes import AgentNodes
from src.models.types import State
from src.tools import lookup_tools
from src.models.types import PurchaseInformation
from src.database.db_operations import lookup, refund
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

def build_graph(tracer=None):
    """Build the agent workflow graph."""
    # Initialize Gemini model for all agent roles
    base_llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        temperature=0,
        convert_system_message_to_human=True,
        top_p=0.8,
        max_output_tokens=1024,
        callbacks=[tracer] if tracer else None
    )
    
    # Create agent nodes
    agent = AgentNodes(
        router_llm=base_llm,
        qa_llm=base_llm,
        info_llm=base_llm
    )
    
    # Build graph
    workflow = StateGraph(state_schema=State)
    
    # Add nodes
    workflow.add_node("route", agent.route_request)
    workflow.add_node("process_music_query", agent.process_music_query)
    workflow.add_node("gather_info", agent.gather_info)
    workflow.add_node("default_response", agent.default_response)
    
    # Configure edges
    workflow.set_entry_point("route")
    workflow.add_conditional_edges(
        "route",
        lambda x: x["next"],
        {
            "gather_info": "gather_info",
            "process_music_query": "process_music_query",
            "default_response": "default_response"
        }
    )
    
    # Add terminal edges
    for node in ["gather_info", "process_music_query", "default_response"]:
        workflow.add_edge(node, END)
    
    return workflow.compile()

__all__ = ["setup_vectorstores", "init_models", "build_graph"]