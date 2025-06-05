from typing import Dict, Any, List, Optional
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END
from src.models.types import State, UserIntent, PurchaseInformation, MusicSearchResult
from src.database.db_operations import lookup, refund
from src.tools.lookup_tools import lookup_track, lookup_album, lookup_artist
from tabulate import tabulate

# Routing instructions for consistent intent classification
ROUTE_INSTRUCTIONS = """You are a customer service agent for an online music store. 
Analyze the user's message and classify it into one of these categories:

1. REFUND - If they mention refund, return, money back, or are unhappy with a purchase
2. MUSIC_QUERY - If they ask about songs, artists, albums, or our music catalog
3. HELLO - If they're greeting or asking what you can do

Return ONLY ONE of these exact words: "refund", "music_query", or "hello"
"""

class AgentNodes:
    def __init__(self, router_llm, qa_llm, info_llm):
        """Initialize agent nodes with language models."""
        self.router_llm = router_llm.with_structured_output(UserIntent)
        self.qa_llm = qa_llm
        self.info_llm = info_llm
        
    async def route_request(self, state: State, config: RunnableConfig) -> Dict[str, Any]:
        """Route the user request to the appropriate node."""
        try:
            user_msg = state["messages"][-1].content
            # Create messages list properly for LLM input
            messages = [
                HumanMessage(content=ROUTE_INSTRUCTIONS),
                HumanMessage(content=user_msg)
            ]
            
            # Use ainvoke with proper message format
            response = await self.router_llm.ainvoke(messages)
            print(f"Router LLM response: {response}")
            
            return {
                "messages": state["messages"],
                "next": {
                    "refund": "gather_info",
                    "music_query": "process_music_query",
                    "hello": "default_response"
                }[response["intent"]]
            }
        except Exception as e:
            print(f"Routing error: {str(e)}")
            return {"messages": state["messages"], "next": "default_response"}

    async def process_music_query(self, state: State, config: RunnableConfig) -> Dict[str, Any]:
        """Process music catalog queries."""
        try:
            user_msg = state["messages"][-1].content
            print(f"Processing music query: {user_msg}")

            try:
                results = await self._search_music(user_msg)

                if results:
                    response = "Here are the matching tracks:\n\n" + self._format_music_results(results)
                else:
                    response = "I couldn't find any tracks matching your query. Could you try being more specific?"
                
            except Exception as lookup_error:
                print(f"Lookup error: {str(lookup_error)}")
                response = "I had trouble searching our music catalog. Please try again."
            
            return {
                "messages": state["messages"] + [AIMessage(content=response)],
                "followup": response,
                "next": END
            }
            
        except Exception as e:
            print(f"Error in process_music_query: {str(e)}")
            error_msg = "I encountered an error while searching our music catalog. Please try again."
            return self._error_response(state, error_msg)

    async def gather_info(self, state: State, config: RunnableConfig) -> Dict[str, Any]:
        """Gather information for refund requests."""
        try:
            info_prompt = """Extract customer purchase information. Required fields:
            - customer_name (if provided)
            - phone (if provided)
            - invoice_id (if provided)
            - track_name or album_title (if provided)
            - purchase_date (if provided)"""

            purchase_info = await self.info_llm.ainvoke({
                "messages": [
                    {"role": "system", "content": info_prompt},
                    {"role": "user", "content": state["messages"][-1].content}
                ]
            })
            
            print(f"Extracted purchase info: {purchase_info}")

            if purchase_info.get("invoice_id"):
                # Process refund with invoice ID
                try:
                    amount = await refund(invoice_id=purchase_info["invoice_id"])
                    response = f"I've processed your refund for ${amount:.2f}. The amount will be credited to your original payment method."
                except Exception as refund_error:
                    print(f"Refund error: {str(refund_error)}")
                    response = "I couldn't process the refund. Please verify the invoice ID and try again."
            else:
                # Request more information
                response = ("To help you with a refund, I need:\n"
                          "- Your invoice ID or\n"
                          "- Your name and the purchase details\n"
                          "Could you please provide this information?")

            return {
                "messages": state["messages"] + [AIMessage(content=response)],
                "followup": response,
                "next": END
            }

        except Exception as e:
            print(f"Error in gather_info: {str(e)}")
            return self._error_response(state, "I encountered an error processing your refund request. Please try again.")

    async def default_response(self, state: State, config: RunnableConfig) -> Dict[str, Any]:
        """Provide default response for greetings or unclear intent."""
        response = ("I'm your music store assistant. I can help you:\n"
                   "• Look up songs, albums, and artists\n"
                   "• Process refunds for purchases\n"
                   "What would you like to do?")
        
        return {
            "messages": state["messages"] + [AIMessage(content=response)],
            "followup": response,
            "next": END
        }

    async def _search_music(self, query: str) -> List[MusicSearchResult]:
        """Helper method to search across all music sources."""
        try:
            results = None
            
            # Try each lookup method in sequence
            if "artist" in query.lower() or "by" in query.lower():
                results = await lookup_artist(query)
            elif "album" in query.lower():
                results = await lookup_album(query)
            else:
                results = await lookup_track(query)
                
            return results or []
        except Exception as e:
            print(f"Search error: {str(e)}")
            return []

    def _format_music_results(self, results: List[MusicSearchResult]) -> str:
        """Format music search results into a table."""
        headers = ["Track", "Artist", "Album", "Duration"]
        rows = [
            [
                result["track_name"],
                result["artist_name"],
                result["album_title"],
                f"{int(result['duration']/1000//60)}:{int(result['duration']/1000%60):02d}"
            ]
            for result in results
        ]
        return tabulate(rows, headers=headers, tablefmt="pipe")

    async def _lookup_purchase(self, info: PurchaseInformation) -> List[Dict]:
        """Look up customer purchase history."""
        try:
            return await lookup(
                customer_first_name=info.get("customer_name", "").split()[0] if info.get("customer_name") else None,
                customer_last_name=info.get("customer_name", "").split()[-1] if info.get("customer_name") else None,
                customer_phone=info.get("phone"),
                track_name=info.get("track_name"),
                album_title=info.get("album_title"),
                purchase_date=info.get("purchase_date")
            )
        except Exception as e:
            print(f"Purchase lookup error: {str(e)}")
            return []

    def _has_required_info(self, info: PurchaseInformation) -> bool:
        """Check if we have enough information to process a refund."""
        return bool(
            info.get("invoice_id") or
            (info.get("customer_name") and (
                info.get("phone") or
                info.get("track_name") or
                info.get("album_title") or
                info.get("purchase_date")
            ))
        )

    def _request_more_info(self, state: State) -> Dict[str, Any]:
        """Create response requesting more customer information."""
        response = ("To help you with your refund, I need:\n"
                   "• Your name and\n"
                   "• Either your phone number or\n"
                   "• Details about what you purchased (song/album name)\n"
                   "Could you please provide these details?")
        
        return {
            "messages": state["messages"] + [AIMessage(content=response)],
            "followup": response,
            "next": END
        }

    def _error_response(self, state: State, message: str) -> Dict[str, Any]:
        """Create a standardized error response."""
        return {
            "messages": state["messages"] + [AIMessage(content=message)],
            "followup": message,
            "next": END
        }