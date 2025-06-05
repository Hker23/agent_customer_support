import asyncio
import streamlit as st
from main import build_graph
from langchain.callbacks.tracers import LangChainTracer
from langchain_core.messages import HumanMessage, AIMessage

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
    tracer = LangChainTracer()
    st.session_state.agent = build_graph(tracer=tracer)

async def process_message(user_input: str):
    """Process a single message through the agent."""
    try:
        messages = [HumanMessage(content=msg["content"]) if msg["role"] == "user" 
                   else AIMessage(content=msg["content"]) 
                   for msg in st.session_state.messages]
        
        state = {
            "messages": messages + [HumanMessage(content=user_input)]
        }
        
        response = await st.session_state.agent.ainvoke(state)
        return response
    except Exception as e:
        st.error(f"Error processing message: {str(e)}")
        return None

# Main chat interface
st.title("Music Store Customer Support")

# Chat input
if prompt := st.chat_input("How can I help you today?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Use asyncio.run for proper async handling
    try:
        response = asyncio.run(process_message(prompt))
        if response:
            st.session_state.messages.append(
                {"role": "assistant", "content": response.get("followup", "")}
            )
    except Exception as e:
        st.error(f"Error: {str(e)}")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])