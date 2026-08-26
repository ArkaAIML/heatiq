def calculate_wbgt_est(temp_c: float, rh: float, solar: float = 0.0) -> float:
    """
    Simplified WBGT estimation for MVP.
    Proper WBGT requires globe temperature.
    """
    # Rough approximation
    e = (rh / 100.0) * 6.105 * (2.71828 ** (17.27 * temp_c / (237.7 + temp_c)))
    wbgt = 0.567 * temp_c + 0.393 * e + 3.94
    if solar > 0:
        wbgt += 1.0 # arbitrary small boost for solar in this simplified proxy
    return round(wbgt, 2)
