from typing import Optional, List, Dict, Tuple
from langchain.tools import tool
from langchain.tools import Tool
from langchain_core.vectorstores import VectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from src.database.db_manager import db_manager
from src.database.db_operations import (
    lookup_track as db_lookup_track,
    lookup_album as db_lookup_album,
    lookup_artist as db_lookup_artist
)
from src.models.types import MusicSearchResult

def setup_vectorstores(embeddings: GoogleGenerativeAIEmbeddings) -> Tuple[VectorStore, VectorStore, VectorStore]:
    """Create vectorstore indexes for all artists, albums, and songs."""
    # Initialize vector stores
    track_store = InMemoryVectorStore(embeddings)
    artist_store = InMemoryVectorStore(embeddings)
    album_store = InMemoryVectorStore(embeddings)

    # Load tracks
    tracks = db_manager.execute_query("SELECT Name FROM Track")
    track_docs = [Document(page_content=row[0], metadata={"type": "track"}) for row in tracks]
    if track_docs:
        track_store.add_documents(track_docs)

    # Load artists
    artists = db_manager.execute_query("SELECT Name FROM Artist")
    artist_docs = [Document(page_content=row[0], metadata={"type": "artist"}) for row in artists]
    if artist_docs:
        artist_store.add_documents(artist_docs)

    # Load albums
    albums = db_manager.execute_query("SELECT Title FROM Album")
    album_docs = [Document(page_content=row[0], metadata={"type": "album"}) for row in albums]
    if album_docs:
        album_store.add_documents(album_docs)

    return track_store, artist_store, album_store

def lookup_track(query: str) -> List[Dict]:
    """Search for tracks in the music database."""
    return db_lookup_track(query)

def lookup_album(query: str) -> List[Dict]:
    """Search for albums in the music database."""
    return db_lookup_album(query)

def lookup_artist(query: str) -> List[Dict]:
    """Search for artists in the music database."""
    return db_lookup_artist(query)

# Create tool instances - removed async/coroutine flags
track_tool = Tool(
    name="lookup_track",
    func=lookup_track,
    description="Search for tracks in the music database"
)

album_tool = Tool(
    name="lookup_album",
    func=lookup_album,
    description="Search for albums in the music database"
)

artist_tool = Tool(
    name="lookup_artist",
    func=lookup_artist,
    description="Search for artists in the music database"
)

__all__ = ['lookup_track', 'lookup_album', 'lookup_artist',
           'track_tool', 'album_tool', 'artist_tool']