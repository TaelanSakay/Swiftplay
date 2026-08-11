def compute_inventory_penalty(
    inventory: float, max_inventory: float, side: str, scaling_factor: float = 1.0
) -> float:
    """
    Computes a penalty to subtract from Expected Value (EV) based on current inventory.

    If inventory is long (positive) and we are trying to buy (side="BUY"),
    the penalty is positive and scales with how close we are to max_inventory.
    If we are trying to sell (side="SELL"), the penalty is negative (a reward).
    """
    # Normalize inventory between -1.0 and 1.0
    normalized_inv = inventory / max_inventory if max_inventory > 0 else 0.0

    # Cap between -1 and 1
    normalized_inv = max(-1.0, min(1.0, normalized_inv))

    if side == "BUY":
        # Positive penalty if already long, negative penalty (reward) if short
        return normalized_inv * scaling_factor
    elif side == "SELL":
        # Positive penalty if already short, negative penalty (reward) if long
        return -normalized_inv * scaling_factor

    return 0.0
