from typing import TypedDict, List, Literal, Optional
from typing_extensions import NotRequired
from langchain_core.messages import BaseMessage

class State(TypedDict):
    """State maintained between nodes."""
    messages: List[BaseMessage]
    next: NotRequired[str]
    followup: NotRequired[str]

class UserIntent(TypedDict):
    """Classification of user intent."""
    intent: Literal["refund", "music_query", "hello"]

class PurchaseInformation(TypedDict):
    """Customer purchase information."""
    customer_name: Optional[str]
    phone: Optional[str]
    invoice_id: Optional[str]
    track_name: Optional[str]
    album_title: Optional[str]
    purchase_date: Optional[str]

class MusicSearchResult(TypedDict):
    """Music search result format."""
    track_name: str
    artist_name: str
    album_title: str
    duration: int  # milliseconds