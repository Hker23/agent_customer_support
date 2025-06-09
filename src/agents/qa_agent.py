from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI  # Updated import
from src.core.tools import lookup_track, lookup_artist, lookup_album
from src.core.models import State
import os
# Agent model
qa_llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.2,
)
qa_graph = create_react_agent(qa_llm, [lookup_track, lookup_artist, lookup_album])