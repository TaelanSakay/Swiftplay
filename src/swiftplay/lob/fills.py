from dataclasses import dataclass


@dataclass
class FillEvent:
    order_id: str
    fill_price: float
    fill_quantity: float
    timestamp: int
    remaining_quantity: float
