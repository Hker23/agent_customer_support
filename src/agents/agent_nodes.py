from typing import Literal, Annotated, Any, Dict, List, Sequence, TypedDict
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import END, StateGraph
from src.models.types import State
from src.database.db_operations import lookup, refund
from src.tools.lookup_tools import lookup_track, lookup_album, lookup_artist
from tabulate import tabulate

# Instructions for extracting the user/purchase info from the conversation.
gather_info_instructions = """You are managing an online music store that sells song tracks. \
Customers can buy multiple tracks at a time and these purchases are recorded in a database as \
an Invoice per purchase and an associated set of Invoice Lines for each purchased track.

Your task is to help customers who would like a refund for one or more of the tracks they've \
purchased. In order for you to be able refund them, the customer must specify the Invoice ID \
to get a refund on all the tracks they bought in a single transaction, or one or more Invoice \
Line IDs if they would like refunds on individual tracks.

Often a user will not know the specific Invoice ID(s) or Invoice Line ID(s) for which they \
would like a refund. In this case you can help them look up their invoices by asking them to \
specify:
- Required: Their first name, last name, and phone number.
- Optionally: The track name, artist name, album name, or purchase date.

If the customer has not specified the required information (either Invoice/Invoice Line IDs \
or first name, last name, phone) then please ask them to specify it."""

# Instructions for the route node to determine intent
route_instructions = """You are managing an online music store that sells song tracks. You need to determine if the user is:
1. Asking for a REFUND on their purchase
2. Asking about MUSIC in our catalog (songs, artists, albums)
3. Just saying HELLO or asking what you can do

Return one of: "refund", "music_query", or "hello"
"""

class RouteResponse(TypedDict):
    """Response from the router node indicating user intent"""
    intent: Literal["refund", "music_query", "hello"]

class AgentNodes:
    def __init__(self, info_llm, qa_llm, router_llm):
        self.info_llm = info_llm
        self.qa_llm = qa_llm
        # Initialize router with structured output directly
        self.router_llm = router_llm.with_structured_output(
            RouteResponse,
            method="openai_function"
        )

    async def gather_info(self, state: State, config: RunnableConfig) -> Dict[str, Any]:
        """Extract purchase information from conversation and determine next step."""
        try:
            # Prepare messages for the LLM
            messages = [
                {"role": "system", "content": gather_info_instructions},
                *[{"role": "user" if isinstance(msg, HumanMessage) else "assistant", 
                   "content": msg.content} for msg in state["messages"]]
            ]
            
            # Call LLM and await response
            info = await self.info_llm.ainvoke(messages)
            
            # Process response with safe dictionary access, handling both direct and function_call responses
            parsed = {}
            if isinstance(info, dict):
                if "function_call" in info.get("additional_kwargs", {}):
                    # Handle function call response
                    func_call = info["additional_kwargs"]["function_call"]
                    if func_call["name"] == "PurchaseInformation":
                        import json
                        try:
                            parsed = json.loads(func_call["arguments"])
                            # Clean up any double-quoted string values
                            for key, value in parsed.items():
                                if isinstance(value, str) and value.startswith('"') and value.endswith('"'):
                                    parsed[key] = value[1:-1]
                        except json.JSONDecodeError:
                            print("Error parsing function call arguments")
                else:
                    # Handle direct response
                    parsed = info.get("parsed", {})
                
                message = str(info.get("raw", info.get("content", "I'm having trouble understanding your request. Could you please rephrase it?")))
            else:
                message = "I'm having trouble understanding your request. Could you please rephrase it?"
            
            # Update state with parsed information
            new_state = {
                "messages": state["messages"] + [AIMessage(content=message)],
                **parsed
            }
            
            # Determine next step
            if any(parsed.get(k) for k in ("invoice_id", "invoice_line_ids")):
                next_step = "process_refund"
            elif all(
                parsed.get(k)
                for k in ("customer_first_name", "customer_last_name", "customer_phone")
            ):
                next_step = "process_lookup"
            else:
                next_step = "default_response"
            
            return {
                **new_state,
                "next": next_step
            }
            
        except Exception as e:
            # Log the error for debugging
            print(f"Error in gather_info: {str(e)}")
            error_msg = "I encountered an error while processing your request. Please try again."
            # Return a user-friendly error message and end the conversation
            return {
                "messages": state["messages"] + [AIMessage(content=error_msg)],
                "followup": error_msg,  # Set followup only when ending
                "next": END
            }

    def process_refund(self, state: State, config: RunnableConfig) -> Dict[str, Any]:
        """Process a refund request."""
        try:
            invoice_id = state.get("invoice_id")
            invoice_line_ids = state.get("invoice_line_ids")
            
            if not any([invoice_id, invoice_line_ids]):
                result = "I apologize, but I couldn't find the invoice ID or line items to refund. Could you please provide those details?"
            else:
                refund_amount = refund(
                    invoice_id=invoice_id, 
                    invoice_line_ids=invoice_line_ids
                )
                result = f"Successfully processed refund for ${refund_amount:.2f}."
        except Exception as e:
            result = f"An error occurred while processing your refund: {str(e)}"

        # Always set followup for terminal nodes
        return {
            "messages": state["messages"] + [AIMessage(content=result)],
            "followup": result,
            "next": END
        }

    def process_lookup(self, state: State, config: RunnableConfig) -> Dict[str, Any]:
        """Process a lookup request."""
        # Validate required customer information
        required_fields = ["customer_first_name", "customer_last_name", "customer_phone"]
        missing_fields = [field for field in required_fields if not state.get(field)]
        
        if missing_fields:
            missing_info = ", ".join(f.replace("customer_", "") for f in missing_fields)
            response = f"I need your {missing_info} to look up your purchases. Could you please provide this information?"
            # Set followup for terminal response
            return {
                "messages": state["messages"] + [AIMessage(content=response)],
                "followup": response,
                "next": END
            }

        try:
            result = lookup(
                customer_first_name=state["customer_first_name"],
                customer_last_name=state["customer_last_name"],
                customer_phone=state["customer_phone"],
                track_name=state.get("track_name"),
                album_title=state.get("album_title"),
                artist_name=state.get("artist_name"),
                purchase_date_iso_8601=state.get("purchase_date")
            )
            
            if not result:
                response = "I couldn't find any purchases matching those details. Please check the information and try again."
            else:
                purchases = []
                for item in result:
                    purchases.append(
                        f"- Invoice Line ID: {item['invoice_line_id']}\n"
                        f"  Track: {item['track_name']}\n"
                        f"  Artist: {item['artist_name']}\n"
                        f"  Purchased: {item['purchase_date']}\n"
                        f"  Quantity: {item['quantity_purchased']}\n"
                        f"  Price: ${item['price_per_unit']:.2f}"
                    )
                response = "Here are your purchases:\n\n" + "\n\n".join(purchases)
                response += "\n\nTo get a refund, please let me know which Invoice Line ID(s) you would like refunded."
        except Exception as e:
            response = f"An error occurred while looking up your purchases: {str(e)}"
        
        # Set followup for terminal response
        return {
            "messages": state["messages"] + [AIMessage(content=response)],
            "followup": response,
            "next": END
        }

    async def route_request(self, state: State, config: RunnableConfig) -> Dict[str, Any]:
        """Route the request to the appropriate handler based on user intent."""
        try:
            # Prepare messages for the router LLM
            messages = [
                {"role": "system", "content": route_instructions},
                *[{"role": "user" if isinstance(msg, HumanMessage) else "assistant", 
                   "content": msg.content} for msg in state["messages"]]
            ]
            
            # Get routing decision from LLM
            response = await self.router_llm.ainvoke(messages)
            
            # Keep track of full state
            new_state = {**state}
            
            # Route based on intent
            if "intent" in response and response["intent"] == "refund":
                new_state["next"] = "gather_info"
            elif "intent" in response and response["intent"] == "music_query":
                new_state["next"] = "process_music_query"
            else:  # hello or fallback
                new_state["next"] = "default_response"
                
            return new_state
            
        except Exception as e:
            print(f"Error in route_request: {str(e)}")
            return {
                **state,
                "next": "default_response"
            }

    async def process_music_query(self, state: State, config: RunnableConfig) -> Dict[str, Any]:
        """Process a music catalog query."""
        try:
            # Get the last user message
            user_msg = state["messages"][-1].content
            
            # Use tools to lookup information
            track_results = lookup_track(artist_name=user_msg)
            album_results = lookup_album(artist_name=user_msg)
            
            # Format response
            response_parts = []
            
            if track_results:
                response_parts.append("Here are the tracks we have:\n")
                track_table = tabulate(track_results, headers="keys", tablefmt="pipe")
                response_parts.append(track_table)
                
            if album_results:
                if response_parts:
                    response_parts.append("\n\n")
                response_parts.append("Albums by this artist:\n")
                album_table = tabulate(album_results, headers="keys", tablefmt="pipe")
                response_parts.append(album_table)
                
            if not track_results and not album_results:
                response = "I couldn't find any music matching your query. Could you try being more specific or try another artist/song name?"
            else:
                response = "\n".join(response_parts)
            
            return {
                "messages": state["messages"] + [AIMessage(content=response)],
                "followup": response,
                "next": END
            }
            
        except Exception as e:
            print(f"Error in process_music_query: {str(e)}")
            error_msg = "I encountered an error while searching our music catalog. Please try again."
            return {
                "messages": state["messages"] + [AIMessage(content=error_msg)],
                "followup": error_msg,
                "next": END
            }

    def default_response(self, state: State, config: RunnableConfig) -> Dict[str, Any]:
        """Handle requests that don't match specific patterns."""
        # Get the last message content
        message = state["messages"][-1].content.lower() if state["messages"] else ""
        
        # Generate appropriate response based on message content
        if "information" in message and "music" in message:
            response = """I can help you with information about our music catalog. You can:
1. Look up songs by artist name
2. Find albums by title
3. Search for specific tracks
4. Check purchase history (if you provide your information)

What specific information would you like to know?"""
        elif any(word in message for word in ["hello", "hi", "hey"]):
            response = """Hello! I'm your music store assistant. I can help you with:
1. Looking up music in our catalog
2. Processing refunds for purchases
3. Finding specific songs, albums, or artists

How can I assist you today?"""
        else:
            response = """I can help you with looking up music in our catalog or processing refunds for your purchases. What would you like to do?
            
- For music lookup, just ask about any artist, album, or song
- For refunds, please provide your name, phone number, or invoice details"""
        
        # Keep track of full state and add response
        new_state = {
            **state,
            "messages": state["messages"] + [AIMessage(content=response)],
            "followup": response,
            "next": END
        }
        
        return new_state

def compile_followup(state: State) -> dict:
    """Set the followup to be the last message if it hasn't explicitly been set."""
    if not state.get("followup"):
        return {"followup": state["messages"][-1].content}
    return {} 