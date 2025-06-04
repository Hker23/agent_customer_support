from typing import Optional, List, Dict, Tuple
from langchain_core.tools import tool
from langchain_core.vectorstores import VectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from src.database.db_manager import db_manager

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

@tool
def lookup_track(
    track_name: Optional[str] = None,
    album_title: Optional[str] = None,
    artist_name: Optional[str] = None,
) -> List[Dict]:
    """Lookup a track in Chinook DB based on identifying information."""
    query = """
    SELECT DISTINCT t.Name as track_name, ar.Name as artist_name, al.Title as album_name
    FROM Track t
    JOIN Album al ON t.AlbumId = al.AlbumId
    JOIN Artist ar ON al.ArtistId = ar.ArtistId
    WHERE 1=1
    """
    params = []

    if track_name:
        query += " AND t.Name LIKE ?"
        params.append(f"%{track_name}%")
    if album_title:
        query += " AND al.Title LIKE ?"
        params.append(f"%{album_title}%")
    if artist_name:
        query += " AND ar.Name LIKE ?"
        params.append(f"%{artist_name}%")

    results = db_manager.execute_query(query, tuple(params))
    
    return [
        {"track_name": row[0], "artist_name": row[1], "album_name": row[2]}
        for row in results
    ]

@tool
def lookup_album(
    track_name: Optional[str] = None,
    album_title: Optional[str] = None,
    artist_name: Optional[str] = None,
) -> List[Dict]:
    """Lookup an album in Chinook DB based on identifying information."""
    query = """
    SELECT DISTINCT al.Title as album_name, ar.Name as artist_name
    FROM Album al
    JOIN Artist ar ON al.ArtistId = ar.ArtistId
    LEFT JOIN Track t ON t.AlbumId = al.AlbumId
    WHERE 1=1
    """
    params = []

    if track_name:
        query += " AND t.Name LIKE ?"
        params.append(f"%{track_name}%")
    if album_title:
        query += " AND al.Title LIKE ?"
        params.append(f"%{album_title}%")
    if artist_name:
        query += " AND ar.Name LIKE ?"
        params.append(f"%{artist_name}%")

    results = db_manager.execute_query(query, tuple(params))
    
    return [{"album_name": row[0], "artist_name": row[1]} for row in results]

@tool
def lookup_artist(
    track_name: Optional[str] = None,
    album_title: Optional[str] = None,
    artist_name: Optional[str] = None,
) -> List[str]:
    """Lookup an artist in Chinook DB based on identifying information."""
    query = """
    SELECT DISTINCT ar.Name as artist_name
    FROM Artist ar
    LEFT JOIN Album al ON al.ArtistId = ar.ArtistId
    LEFT JOIN Track t ON t.AlbumId = al.AlbumId
    WHERE 1=1
    """
    params = []

    if track_name:
        query += " AND t.Name LIKE ?"
        params.append(f"%{track_name}%")
    if album_title:
        query += " AND al.Title LIKE ?"
        params.append(f"%{album_title}%")
    if artist_name:
        query += " AND ar.Name LIKE ?"
        params.append(f"%{artist_name}%")

    results = db_manager.execute_query(query, tuple(params))
    
    return [row[0] for row in results] 