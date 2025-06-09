import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Set up Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

# Load environment variables
load_dotenv()

# External library imports
import streamlit as st
from langgraph.graph import END, StateGraph
from langgraph.types import Command
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import add_messages
from typing import Literal, TypedDict, Annotated
from langsmith import Client
# Local imports
from src.core.models import State, UserIntent
from src.agents.refund_agent import refund_graph
from src.agents.qa_agent import qa_graph
from src.core.database import download_chinook_db

client = Client()
class LangSmithTracer(BaseCallbackHandler):
    def __init__(self, client: Client, project_name: str):
        self.client = client
        self.project_name = project_name
        self.project_name = project_name
        
    def on_llm_start(self, *args, **kwargs):
        self.client.create_run(
            name="LLM Call",
            run_type="llm",
            project_name=self.project_name,
            inputs=kwargs.get("prompts", [])
        )

tracer = LangSmithTracer(
    client=client,
    project_name="chinook-customer-support"
)

# Add to your config when invoking the graph
config = RunnableConfig(
    callbacks=[tracer],
    configurable={"env": "prod"}
)



# Ensure database is downloaded
if not os.path.exists("data/Chinook.db"):
    os.makedirs("data", exist_ok=True)
    download_chinook_db()


# Define router LLM and instructions
router_llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash").with_structured_output(
    UserIntent, method="json_schema", strict=True
)
route_instructions ="""You are managing an online music store that sells song tracks. \
You can help customers in two types of ways: (1) answering general questions about \
tracks sold at your store, (2) helping them get a refund on a purhcase they made at your store.

Based on the following conversation, determine if the user is currently seeking general \
information about song tracks or if they are trying to refund a specific purchase.

Return 'refund' if they are trying to get a refund and 'question_answering' if they are \
asking a general music question. Do NOT return anything else. Do NOT try to respond to \
the user.
"""

# Node for routing (remove async)
def intent_classifier(state: State) -> Command[Literal["refund_agent", "qa_agent"]]:
    """Routes user requests to appropriate agent based on intent."""
    try:
        response = router_llm.invoke(
            [
                {"role": "system", "content": route_instructions},
                *state["messages"]
            ]
        )
        
        # Map the intent to the corresponding agent
        intent = response.get("intent", "question_answering")
        agent_name = "refund_agent" if intent == "refund" else "qa_agent"
        
        return Command(
            update={"messages": state["messages"]},
            goto=agent_name
        )
    except Exception as e:
        print(f"Error in intent classifier: {str(e)}")
        return Command(
            update={
                "messages": [*state["messages"], {"role": "assistant", "content": "I'm sorry, I couldn't understand that. Could you rephrase?"}],
                "followup": "I'm sorry, I couldn't understand that. Could you rephrase?"
            },
            goto=END
        )

# Node for making sure the 'followup' key is set before our agent run completes.
def compile_followup(state: State) -> dict:
    """Set the followup to be the last message if it hasn't explicitly been set."""
    if not state.get("followup"):
        messages = state.get("messages", [])
        if messages:
            last_message = messages[-1]
            # Handle both AIMessage objects and dict messages
            if hasattr(last_message, "content"):
                return {"followup": last_message.content}
            elif isinstance(last_message, dict) and "content" in last_message:
                return {"followup": last_message["content"]}
    return {"followup": "I apologize, something went wrong."}

# Agent definition for the live application
app_builder = StateGraph(State)

# Add nodes
app_builder.add_node("intent_classifier", intent_classifier)
app_builder.add_node("refund_agent", refund_graph)
app_builder.add_node("qa_agent", qa_graph)
app_builder.add_node("compile_followup", compile_followup)  # Add this node

# Set entry point
app_builder.set_entry_point("intent_classifier")

# Add edges
app_builder.add_edge("refund_agent", "compile_followup")
app_builder.add_edge("qa_agent", "compile_followup")
app_builder.add_edge("compile_followup", END)

# Compile graph
app_graph = app_builder.compile()


st.title("Chinook Music Store Customer Service")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# React to user input
if prompt := st.chat_input("What can I help you with?"):
    # Display user message in chat message container
    st.chat_message("user").markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Run the graph
    with st.spinner("Thinking..."):
        # Prepare initial state for the graph
        initial_state = {"messages": [{"role": "user", "content": prompt}]}
        
        result = app_graph.invoke(
            initial_state,
            config=config
        )

        # Get the response (assuming the 'followup' key is set by the graph's last node)
        response = result.get("followup", "I'm sorry, I couldn't process that request.")

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        st.markdown(response)
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})