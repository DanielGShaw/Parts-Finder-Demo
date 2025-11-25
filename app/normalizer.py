from __future__ import annotations
from typing import Dict, List, Any
import pandas as pd

# Category normalization - maps variations to canonical names
CATEGORY_ALIASES = {
    "cabin air filter": "Cabin Filter",
    "cabin filter": "Cabin Filter",
    "cabin pollen filter": "Cabin Filter",
    "air filter": "Air Filter",
    "oil filter": "Oil Filter",
}

def normalize_category(category: str) -> str:
    """Normalize category name to canonical form for consistent grouping."""
    if not category:
        return category
    lower = category.lower().strip()
    return CATEGORY_ALIASES.get(lower, category)

def _to_float(x):
    try:
        if isinstance(x, str):
            x = x.replace("$", "").replace(",", "").strip()
        return float(x)
    except Exception:
        return None

SUPPLIER_BASE_URLS = {
    "AutoParts Direct": "https://autopartsdirect.example.com",
    "PartsHub Pro": "https://partshubpro.example.com",
}

def _parse_qty_for_sort(qty_str: Any) -> int:
    """
    Converts an availability quantity string to a sortable integer.

    Returns:
        - Actual numeric quantities: 1, 2, 10, 14, etc.
        - Available (no specific qty): 999 (sorts as in-stock)
        - Not available: 0
    """
    if qty_str is None:
        return 0
    if isinstance(qty_str, int):
        return qty_str

    s = str(qty_str).strip().lower()
    if s in ('n/a', '-', ''):
        return 0

    # Handle cases where availability is indicated but no specific quantity is given
    # These should be treated as having stock (return high number to sort above items with qty=0)
    if s in ('available', 'in stock', 'yes'):
        return 999

    # Handle special availability strings that indicate no stock
    if s in ('call for availability', 'call to order', 'special order', 'not available'):
        return 0

    if s.endswith('+'):
        s = s[:-1]

    try:
        return int(s)
    except ValueError:
        return 0

def _format_availability_display(is_available: bool, qty_raw: Any) -> str:
    """
    Creates a user-friendly availability display string.

    Examples:
        - is_available=True, qty_raw="10" → "Available locally (Qty: 10)"
        - is_available=True, qty_raw="Available" → "Available locally"
        - is_available=False, qty_raw="Special Order" → "Special Order"
        - is_available=False, qty_raw="0" → "Not Available"
    """
    if not is_available:
        # Not available cases
        if qty_raw in ['Special Order', 'Call for Availability', 'Call to Order']:
            return str(qty_raw)
        return 'Not Available'

    # Available cases
    if qty_raw in ['Available', 'In Stock', 'Yes', 'available', 'in stock', 'yes']:
        return 'Available locally'

    # Try to parse as numeric quantity
    try:
        qty_num = int(str(qty_raw).strip())
        if qty_num > 0:
            return f'Available locally (Qty: {qty_num})'
        else:
            return 'Not Available'
    except (ValueError, TypeError):
        # If we can't parse it but it's marked as available, show generic message
        return 'Available locally'

def normalize_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Map raw supplier fields from the Part dataclass (as a dict) to a common schema."""
    supplier = raw.get("supplier")
    product_url = raw.get("product_url")

    # Construct absolute URL if the product URL is relative
    if product_url and product_url.startswith('/') and supplier in SUPPLIER_BASE_URLS:
        product_url = SUPPLIER_BASE_URLS[supplier] + product_url

    availability_info = raw.get("availability") or {}
    local_availability = availability_info.get("local", {})

    is_available_flag = local_availability.get("available", False)
    qty_raw = local_availability.get("qty")

    # Create three separate availability fields:
    # 1. availability_qty_display: Original raw value for reference
    # 2. availability_qty_sort: Sortable integer for backend sorting
    # 3. availability: User-friendly display string
    qty_display = qty_raw if qty_raw is not None else "N/A"
    qty_sort = _parse_qty_for_sort(qty_raw)
    availability_str = _format_availability_display(is_available_flag, qty_raw) if local_availability else "Unknown"

    cost_ex_gst = _to_float(raw.get("cost_ex_gst"))
    cost_inc_gst = cost_ex_gst * 1.1 if cost_ex_gst is not None else None

    return {
        "supplier": supplier,
        "part_no": raw.get("code"),
        "description": raw.get("description"),
        "rrp_inc_gst": _to_float(raw.get("rrp_inc_gst")),
        "cost_ex_gst": cost_ex_gst,
        "cost_inc_gst": cost_inc_gst,
        "availability": availability_str,
        "is_available": is_available_flag,
        "availability_qty_display": qty_display,      # Original raw value
        "availability_qty_sort": qty_sort,            # Sortable integer
        "category": normalize_category(raw.get("category")),
        "brand": raw.get("brand"),
        "url": product_url,
        "_raw": raw,
    }

def normalize_results(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [normalize_row(r) for r in rows]

def dedupe_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate by (supplier, part_no)."""
    if "part_no" in df.columns:
        norm = df["part_no"].astype(str).str.replace(r"\s+", "", regex=True).str.upper()
        df = df.assign(_key=norm)
        df = df.drop_duplicates(subset=["supplier", "_key"], keep="first")
        df = df.drop(columns=["_key"])
    else:
        keep_cols = [c for c in ["description", "price"] if c in df.columns]
        if keep_cols:
            df = df.drop_duplicates(subset=keep_cols, keep="first")
    return df.reset_index(drop=True)
