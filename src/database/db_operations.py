from typing import Optional, List, Dict
from src.database.db_manager import db_manager

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

def lookup(
    customer_first_name: str,
    customer_last_name: str,
    customer_phone: str,
    track_name: Optional[str] = None,
    album_title: Optional[str] = None,
    artist_name: Optional[str] = None,
    purchase_date_iso_8601: Optional[str] = None,
) -> List[Dict]:
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

    params = [customer_first_name, customer_last_name, customer_phone]

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

    results = db_manager.execute_query(query, tuple(params))

    return [
        {
            "invoice_line_id": row[0],
            "track_name": row[1],
            "artist_name": row[2],
            "purchase_date": row[3],
            "quantity_purchased": row[4],
            "price_per_unit": row[5],
        }
        for row in results
    ] 