from dataclasses import dataclass
from typing import Optional
from decimal import Decimal


@dataclass
class Part:
    supplier: str                 # e.g. "AutoParts Direct"
    category: str                 # "Oil Filter"
    code: str                     # e.g. "APD-1125"
    description: str              # the free text line under code
    rrp_inc_gst: Optional[Decimal]  # 8.14
    cost_ex_gst: Optional[Decimal]  # 4.69
    product_url: str              # /products/APD-1125
    image_url: Optional[str]
    brand: Optional[str]          # from <img alt="BrandA">
    groups: Optional[str]
    notes: Optional[str]
    per_car_qty: Optional[str]
    availability: Optional[dict]  # normalized availability once fetched
