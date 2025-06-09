# src/core/tools.py
import sqlite3
import os
from typing import Literal, List, Dict
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.tools import tool
from src.core.database import get_db_connection # Import the database connection

def _refund(invoice_id: int | None, invoice_line_ids: list[int] | None, mock: bool = False) -> float:
    """Given an Invoice ID and/or Invoice Line IDs, delete the relevant Invoice/InvoiceLine records in the Chinook DB.

    Args:
        invoice_id: The Invoice to delete.
        invoice_line_ids: The Invoice Lines to delete.
        mock: If True, do not actually delete the specified Invoice/Invoice Lines. Used for testing purposes.

    Returns:
        float: The total dollar amount that was deleted (or mock deleted).
    """

    if invoice_id is None and invoice_line_ids is None:
        return 0.0

    # Connect to the Chinook database
    with get_db_connection() as conn:
        cursor = conn.cursor()

        total_refund = 0.0

        try:
            # If invoice_id is provided, delete entire invoice and its lines
            if invoice_id is not None:
                # First get the total amount for the invoice
                cursor.execute(
                    """
                    SELECT Total
                    FROM Invoice
                    WHERE InvoiceId = ?
                """,
                    (invoice_id,),
                )

                result = cursor.fetchone()
                if result:
                    total_refund += result[0]

                # Delete invoice lines first (due to foreign key constraints)
                if not mock:
                    cursor.execute(
                        """
                        DELETE FROM InvoiceLine
                        WHERE InvoiceId = ?
                    """,
                        (invoice_id,),
                    )

                    # Then delete the invoice
                    cursor.execute(
                        """
                        DELETE FROM Invoice
                        WHERE InvoiceId = ?
                    """,
                        (invoice_id,),
                    )

            # If specific invoice lines are provided
            if invoice_line_ids is not None:
                # Get the total amount for the specified invoice lines
                placeholders = ",".join(["?" for _ in invoice_line_ids])
                cursor.execute(
                    f"""
                    SELECT SUM(UnitPrice * Quantity)
                    FROM InvoiceLine
                    WHERE InvoiceLineId IN ({placeholders})
                """,
                    invoice_line_ids,
                )

                result = cursor.fetchone()
                if result and result[0]:
                    total_refund += result[0]

                if not mock:
                    # Delete the specified invoice lines
                    cursor.execute(
                        f"""
                        DELETE FROM InvoiceLine
                        WHERE InvoiceLineId IN ({placeholders})
                    """,
                        invoice_line_ids,
                    )

            # Commit the changes
            conn.commit()

        except sqlite3.Error as e:
            # Roll back in case of error
            conn.rollback()
            raise e

        finally:
            # Close the connection
            conn.close()

        return float(total_refund)


def _lookup(
    customer_first_name: str,
    customer_last_name: str,
    customer_phone: str,
    track_name: str | None,
    album_title: str | None,
    artist_name: str | None,
    purchase_date_iso_8601: str | None,
) -> list[dict]:
    """Find all of the Invoice Line IDs in the Chinook DB for the given filters.

    Returns:
        a list of dictionaries that contain keys: {
            'invoice_line_id',
            'track_name',
            'artist_name',
            'purchase_date',
            'quantity_purchased',
            'price_per_unit'
        }
    """

    # Connect to the database
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Base query joining all necessary tables
        query = """
        SELECT
            il.InvoiceLineId,
            t.Name as track_name,
            art.Name as artist_name,
            i.InvoiceDate as purchase_date,
            il.Quantity as quantity_purchased,
            il.UnitPrice as price_per_unit
        FROM InvoiceLine il
        JOIN Invoice i ON il.InvoiceId = i.InvoiceId
        JOIN Customer c ON i.CustomerId = c.CustomerId
        JOIN Track t ON il.TrackId = t.TrackId
        JOIN Album alb ON t.AlbumId = alb.AlbumId
        JOIN Artist art ON alb.ArtistId = art.ArtistId
        WHERE c.FirstName = ?
        AND c.LastName = ?
        AND c.Phone = ?
        """

        # Parameters for the query
        params = [customer_first_name, customer_last_name, customer_phone]

        # Add optional filters
        if track_name:
            query += " AND t.Name = ?"
            params.append(track_name)

        if album_title:
            query += " AND alb.Title = ?"
            params.append(album_title)

        if artist_name:
            query += " AND art.Name = ?"
            params.append(artist_name)

        if purchase_date_iso_8601:
            query += " AND date(i.InvoiceDate) = date(?)"
            params.append(purchase_date_iso_8601)

        # Execute query
        cursor.execute(query, params)

        # Fetch results
        results = cursor.fetchall()

        # Convert results to list of dictionaries
        output = []
        for row in results:
            output.append(
                {
                    "invoice_line_id": row[0],
                    "track_name": row[1],
                    "artist_name": row[2],
                    "purchase_date": row[3],
                    "quantity_purchased": row[4],
                    "price_per_unit": row[5],
                }
            )

        # Close connection
        conn.close()

        return output


# Update lookup_track, lookup_album, lookup_artist similarly
@tool
def lookup_track(
    track_name: str | None = None,
    album_title: str | None = None,
    artist_name: str | None = None,
) -> list[dict]:
    """Lookup a track in Chinook DB based on identifying information about.

    Returns:
        a list of dictionaries per matching track that contain keys {'track_name', 'artist_name', 'album_name'}
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
        SELECT DISTINCT t.Name as track_name, ar.Name as artist_name, al.Title as album_name
        FROM Track t
        JOIN Album al ON t.AlbumId = al.AlbumId
        JOIN Artist ar ON al.ArtistId = ar.ArtistId
        WHERE 1=1
        """
        params = []

        if track_name:
            track_name = track_store.similarity_search(track_name, k=1)[0].page_content
            query += " AND t.Name LIKE ?"
            params.append(f"%{track_name}%")
        if album_title:
            album_title = album_store.similarity_search(album_title, k=1)[0].page_content
            query += " AND al.Title LIKE ?"
            params.append(f"%{album_title}%")
        if artist_name:
            artist_name = artist_store.similarity_search(artist_name, k=1)[0].page_content
            query += " AND ar.Name LIKE ?"
            params.append(f"%{artist_name}%")

        cursor.execute(query, params)
        results = cursor.fetchall()

        tracks = [
            {"track_name": row[0], "artist_name": row[1], "album_name": row[2]}
            for row in results
        ]

        conn.close()
        return tracks

@tool
def lookup_album(
    track_name: str | None = None,
    album_title: str | None = None,
    artist_name: str | None = None,
) -> list[dict]:
    """Lookup an album in Chinook DB based on identifying information about.

    Returns:
        a list of dictionaries per matching album that contain keys {'album_name', 'artist_name'}
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()

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
        cursor.execute(query, params)
        results = cursor.fetchall()

        albums = [{"album_name": row[0], "artist_name": row[1]} for row in results]

        conn.close()
        return albums

@tool
def lookup_artist(
    track_name: str | None = None,
    album_title: str | None = None,
    artist_name: str | None = None,
) -> list[str]:
    """Lookup an album in Chinook DB based on identifying information about.

    Returns:
        a list of matching artist names
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()

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

        cursor.execute(query, params)
        results = cursor.fetchall()
        artists = [row[0] for row in results]

        conn.close()
        return artists

def index_fields() -> (
    tuple[InMemoryVectorStore, InMemoryVectorStore, InMemoryVectorStore]
):
    conn = None # Initialize conn to None
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            tracks = cursor.execute("SELECT Name FROM Track").fetchall()
            artists = cursor.execute("SELECT Name FROM Artist").fetchall()
            albums = cursor.execute("SELECT Title FROM Album").fetchall()
    finally:
        if conn:
            conn.close()
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )
    

    track_store = InMemoryVectorStore(embeddings)
    artist_store = InMemoryVectorStore(embeddings)
    album_store = InMemoryVectorStore(embeddings)

    track_store.add_texts([t[0] for t in tracks])
    artist_store.add_texts([a[0] for a in artists])
    album_store.add_texts([a[0] for a in albums])
    return track_store, artist_store, album_store
# These will be initialized once when the module is imported
track_store, artist_store, album_store = index_fields()