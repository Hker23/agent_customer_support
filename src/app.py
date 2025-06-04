import streamlit as st
import asyncio
from langchain.callbacks.tracers import LangChainTracer
from langchain_core.messages import HumanMessage
from langchain_core.callbacks import CallbackManager

from utils.config import setup_langsmith
from main import build_graph

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "initialized" not in st.session_state:
    st.session_state.initialized = False

if "trace_urls" not in st.session_state:
    st.session_state.trace_urls = {}

def initialize_app():
    """Initialize the application components."""
    if not st.session_state.initialized:
        # Setup LangSmith
        try:
            # Setup LangSmith with proper tracing
            setup_langsmith()  # Ensure API keys are set
            tracer = LangChainTracer(project_name="music-store-support")
            graph = build_graph(tracer)  # Pass tracer to graph builder
            
            st.session_state.graph = graph
            st.session_state.tracer = tracer
            st.session_state.initialized = True
        except Exception as e:
            st.error(f"Failed to initialize app: {str(e)}")
            return False
    return True

async def process_message(message: str) -> str:
    """Process a message through the agent with tracing."""
    try:
        # Setup state with message
        initial_state = {
            "messages": [HumanMessage(content=message)],
            "followup": None
        }
        
        # Process through graph with tracing
        tracer = st.session_state.tracer
        result = await st.session_state.graph.ainvoke(
            initial_state,
            config={
                "callbacks": [tracer],
                "metadata": {"conversation": message}
            }
        )
        
        # Let the tracer finish persisting the run
        await asyncio.sleep(0.5)  # Give LangSmith a moment to process
        
        # Try to get the latest run
        try:
            if hasattr(tracer, "client"):
                runs = list(tracer.client.list_runs(
                    project_name="music-store-support",
                    error=False,
                    limit=1
                ))
                if runs:
                    latest_run = runs[0]
                    base_url = "https://smith.langchain.com"
                    trace_url = f"{base_url}/projects/music-store-support/traces/{latest_run.id}"
                    st.session_state.trace_urls[message] = trace_url
                    st.sidebar.markdown(f"Latest Trace: [View]({trace_url})")
                    
                    # Show all traces in reverse chronological order
                    if st.session_state.trace_urls:
                        st.sidebar.markdown("### All Traces")
                        for msg, url in reversed(list(st.session_state.trace_urls.items())):
                            st.sidebar.markdown(f"- [{msg[:30]}...]({url})")
        except Exception as trace_err:
            st.sidebar.warning("Trace URL not available")
            print(f"Could not get trace URL: {trace_err}")
        
        return result.get("followup", "I'm sorry, I couldn't process your request.")
            
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return "I encountered an error processing your request."

def main():
    st.title("Music Store Support")
    
    # Initialize app
    if not initialize_app():
        return

    # Chat interface
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Handle user input
    if prompt := st.chat_input("How can I help you today?"):
        # Show user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get and show response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = asyncio.run(process_message(prompt))
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main() 