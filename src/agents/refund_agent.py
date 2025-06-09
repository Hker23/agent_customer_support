import json
from typing import Literal, TypedDict, Dict, Annotated
from langgraph.graph import END, StateGraph
from langgraph.types import Command
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from src.core.models import State, PurchaseInformation
from src.core.tools import _refund, _lookup
from tabulate import tabulate

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
info_llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro-latest",
    temperature=0,
    convert_system_message_to_human=True
).with_structured_output(PurchaseInformation)

def gather_info(state: State) -> Command[Literal["lookup_action", "refund_action", END]]:
    """Gathers information needed for refund processing"""
    try:
        # Extract user's message
        user_message = state["messages"][-1].content if state["messages"] else ""
        
        # Get structured information
        parsed = info_llm.invoke([
            {"role": "system", "content": gather_info_instructions},
            {"role": "user", "content": user_message}
        ])
        
        # Determine next action and prepare response
        if any(parsed.get(k) for k in ("invoice_id", "invoice_line_ids")):
            response = "I'll help you process that refund right away."
            goto = "refund_action"
        elif all(parsed.get(k) for k in ("customer_name", "phone")):
            response = "Let me look up your purchase history."
            goto = "lookup_action"
        else:
            response = ("To help you with a refund, I need:\n"
                       "• Your full name\n"
                       "• Phone number\n"
                       "Could you please provide these details?")
            goto = END
            
        # Create state update
        update = {
            "messages": [{"role": "assistant", "content": response}]
        }
        update.update(parsed)  # Add parsed fields to state
        
        return Command(update=update, goto=goto)
        
    except Exception as e:
        print(f"Error in gather_info: {str(e)}")
        error_msg = ("I'm having trouble processing your refund request. "
                    "Could you please provide your name and phone number?")
        return Command(
            update={"messages": [{"role": "assistant", "content": error_msg}]},
            goto=END
        )

def refund(state: State, config: RunnableConfig) -> Dict:
    """Process refund for specified purchases"""
    mock = config.get("configurable", {}).get("env", "prod") == "test"
    refunded = _refund(
        invoice_id=state.get("invoice_id"),
        invoice_line_ids=state.get("invoice_line_ids"),
        mock=mock
    )
    response = f"You have been refunded a total of: ${refunded:.2f}. Is there anything else I can help with?"
    return {"messages": [{"role": "assistant", "content": response}]}

def lookup(state: State) -> Dict:
    """Look up purchase information based on customer details"""
    args = (
        state.get(k)
        for k in (
            "customer_first_name",
            "customer_last_name",
            "customer_phone",
            "track_name",
            "album_title",
            "artist_name",
            "purchase_date_iso_8601",
        )
    )
    results = _lookup(*args)
    
    if not results:
        response = "No purchases found. Please check your information."
    else:
        headers = ["Track", "Artist", "Purchase Date", "Quantity", "Price"]
        rows = [[
            r["track_name"],
            r["artist_name"],
            r["purchase_date"],
            r["quantity_purchased"],
            f"${r['price_per_unit']:.2f}"
        ] for r in results]
        table = tabulate(rows, headers=headers, tablefmt="pipe")
        response = f"Here are the purchases I found:\n\n{table}\n\nWould you like a refund for any of these items?"

    return {"messages": [{"role": "assistant", "content": response}]}

# Graph construction
graph_builder = StateGraph(State)
graph_builder.add_node("gather_info", gather_info)
graph_builder.add_node("refund_action", refund)
graph_builder.add_node("lookup_action", lookup)

graph_builder.set_entry_point("gather_info")
graph_builder.add_edge("gather_info", "refund_action")
graph_builder.add_edge("gather_info", "lookup_action")
graph_builder.add_edge("lookup_action", END)
graph_builder.add_edge("refund_action", END)

refund_graph = graph_builder.compile()