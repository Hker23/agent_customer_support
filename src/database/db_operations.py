from typing import Optional, List, Dict
from datetime import datetime
from src.database.db_manager import db_manager
import asyncio

def refund(
    invoice_id: Optional[int], 
    invoice_line_ids: Optional[List[int]], 
    mock: bool = False
) -> float:
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

    total_refund = 0.0

    try:
        if invoice_id is not None:
            result = db_manager.execute_query(
                "SELECT Total FROM Invoice WHERE InvoiceId = ?",
                (invoice_id,)
            )
            if result:
                total_refund += result[0][0]

            if not mock:
                db_manager.execute_query(
                    "DELETE FROM InvoiceLine WHERE InvoiceId = ?",
                    (invoice_id,)
                )
                db_manager.execute_query(
                    "DELETE FROM Invoice WHERE InvoiceId = ?",
                    (invoice_id,)
                )

        if invoice_line_ids:
            placeholders = ",".join(["?" for _ in invoice_line_ids])
            result = db_manager.execute_query(
                f"SELECT SUM(UnitPrice * Quantity) FROM InvoiceLine WHERE InvoiceLineId IN ({placeholders})",
                tuple(invoice_line_ids)
            )
            if result and result[0][0]:
                total_refund += result[0][0]

            if not mock:
                db_manager.execute_query(
                    f"DELETE FROM InvoiceLine WHERE InvoiceLineId IN ({placeholders})",
                    tuple(invoice_line_ids)
                )

    except Exception as e:
        raise e

    return float(total_refund)

async def lookup_track(query: str) -> List[Dict]:
    """Async lookup for tracks."""
    sql = """
    SELECT DISTINCT
        Track.Name as track_name, 
        Artist.Name as artist_name, 
        Album.Title as album_title,
        Track.Milliseconds as duration
    FROM Track
    JOIN Album ON Track.AlbumId = Album.AlbumId
    JOIN Artist ON Album.ArtistId = Artist.ArtistId
    WHERE LOWER(Track.Name) LIKE LOWER(?)
    """
    
    # Run DB query in thread pool
    results = await asyncio.to_thread(
        db_manager.execute_query,
        sql,
        [f"%{query}%"]
    )
    
    return [
        {
            "track_name": row[0],
            "artist_name": row[1],
            "album_title": row[2],
            "duration": row[3]
        }
        for row in results
    ]

def lookup_album(query: str) -> List[Dict]:
    """Look up albums in the database."""
    sql = """
    SELECT DISTINCT
        Track.Name as track_name, 
        Artist.Name as artist_name, 
        Album.Title as album_title,
        Track.Milliseconds as duration
    FROM Album
    JOIN Track ON Album.AlbumId = Track.AlbumId
    JOIN Artist ON Album.ArtistId = Artist.ArtistId
    WHERE LOWER(Album.Title) LIKE LOWER(?)
    """
    results = db_manager.execute_query(sql, [f"%{query}%"])
    
    return [
        {
            "track_name": row[0],
            "artist_name": row[1],
            "album_title": row[2],
            "duration": row[3]
        }
        for row in results
    ]

def lookup_artist(query: str) -> List[Dict]:
    """Look up artists in the database."""
    sql = """
    SELECT DISTINCT
        Track.Name as track_name, 
        Artist.Name as artist_name, 
        Album.Title as album_title,
        Track.Milliseconds as duration
    FROM Track
    JOIN Album ON Track.AlbumId = Album.AlbumId
    JOIN Artist ON Album.ArtistId = Artist.ArtistId
    WHERE LOWER(Artist.Name) LIKE LOWER(?)
    """
    # Extract artist name from query
    artist_name = query.lower().replace("tracks by ", "").replace("songs by ", "")
    search_term = f"%{artist_name}%"
    
    print(f"Searching for artist: {search_term}")
    results = db_manager.execute_query(sql, [search_term])
    
    return [
        {
            "track_name": row[0],
            "artist_name": row[1],
            "album_title": row[2],
            "duration": row[3]
        }
        for row in results
    ]

async def lookup(
    customer_first_name: Optional[str] = None,
    customer_last_name: Optional[str] = None,
    customer_phone: Optional[str] = None,
    track_name: Optional[str] = None,
    album_title: Optional[str] = None,
    artist_name: Optional[str] = None,
    purchase_date: Optional[str] = None
) -> List[Dict]:
    """Look up customer purchases based on provided criteria."""
    conditions = []
    params = []
    
    if customer_first_name:
        conditions.append("LOWER(Customer.FirstName) LIKE LOWER(?)")
        params.append(f"%{customer_first_name}%")
    
    if customer_last_name:
        conditions.append("LOWER(Customer.LastName) LIKE LOWER(?)")
        params.append(f"%{customer_last_name}%")
        
    if customer_phone:
        conditions.append("Customer.Phone LIKE ?")
        params.append(f"%{customer_phone}%")
        
    if track_name:
        conditions.append("LOWER(Track.Name) LIKE LOWER(?)")
        params.append(f"%{track_name}%")
        
    if album_title:
        conditions.append("LOWER(Album.Title) LIKE LOWER(?)")
        params.append(f"%{album_title}%")
        
    if artist_name:
        conditions.append("LOWER(Artist.Name) LIKE LOWER(?)")
        params.append(f"%{artist_name}%")
        
    if purchase_date:
        conditions.append("DATE(Invoice.InvoiceDate) = DATE(?)")
        params.append(purchase_date)
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    sql = f"""
    SELECT DISTINCT
        InvoiceLine.InvoiceLineId,
        Track.Name as track_name,
        Artist.Name as artist_name,
        Invoice.InvoiceDate as purchase_date,
        InvoiceLine.UnitPrice as price_per_unit
    FROM Customer
    JOIN Invoice ON Customer.CustomerId = Invoice.CustomerId
    JOIN InvoiceLine ON Invoice.InvoiceId = InvoiceLine.InvoiceId
    JOIN Track ON InvoiceLine.TrackId = Track.TrackId
    JOIN Album ON Track.AlbumId = Album.AlbumId
    JOIN Artist ON Album.ArtistId = Artist.ArtistId
    WHERE {where_clause}
    ORDER BY Invoice.InvoiceDate DESC
    """
    
    results = db_manager.execute_query(sql, params)
    return [
        {
            "invoice_line_id": row[0],
            "track_name": row[1],
            "artist_name": row[2],
            "purchase_date": row[3],
            "price_per_unit": row[4]
        }
        for row in results
    ]