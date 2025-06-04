from typing import Any, Callable
from langgraph.graph import StateGraph
from langchain.callbacks.tracers import LangChainTracer
import inspect

def create_traced_node(
    graph: StateGraph,
    name: str,
    func: Callable,
    tracer: LangChainTracer
) -> None:
    """Add a node to the graph with tracing enabled."""
    async def async_traced_func(state: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        # Pass through the tracer in config
        if "callbacks" not in config:
            config["callbacks"] = [tracer]
            
        # Execute async function
        return await func(state, config)
        
    def sync_traced_func(state: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        # Pass through the tracer in config
        if "callbacks" not in config:
            config["callbacks"] = [tracer]
            
        # Execute sync function
        return func(state, config)
    
    # Use appropriate wrapper based on whether func is async
    traced_func = async_traced_func if inspect.iscoroutinefunction(func) else sync_traced_func
    graph.add_node(name, traced_func) 