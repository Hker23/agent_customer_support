from typing import List, Optional
from typing_extensions import Annotated, TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from langgraph.channels import last_value

class State(TypedDict):
    """Agent state."""
    messages: Annotated[List[AnyMessage], add_messages]
    followup: Annotated[Optional[str], last_value]
    invoice_id: Optional[int]
    invoice_line_ids: Optional[List[int]]
    customer_first_name: Optional[str]
    customer_last_name: Optional[str]
    customer_phone: Optional[str]
    track_name: Optional[str]
    album_title: Optional[str]
    artist_name: Optional[str]
    purchase_date_iso_8601: Optional[str]

class PurchaseInformation(TypedDict):
    """All of the known information about the invoice / invoice lines the customer would like refunded."""
    invoice_id: Optional[int]
    invoice_line_ids: Optional[List[int]]
    customer_first_name: Optional[str]
    customer_last_name: Optional[str]
    customer_phone: Optional[str]
    track_name: Optional[str]
    album_title: Optional[str]
    artist_name: Optional[str]
    purchase_date_iso_8601: Optional[str]
    followup: Annotated[Optional[str], "If the user hasn't enough identifying information, please tell them what the required information is and ask them to specify it."]

class UserIntent(TypedDict):
    """The user's current intent in the conversation"""
    intent: str  # Literal["refund", "question_answering"]

class Grade(TypedDict):
    """Compare the expected and actual answers and grade the actual answer."""
    reasoning: Annotated[str, "Explain your reasoning for whether the actual response is correct or not."]
    is_correct: Annotated[bool, "True if the student response is mostly or exactly correct, otherwise False."] 