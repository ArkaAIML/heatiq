def calculate_heat_index(temp_c: float, rh: float) -> float:
    """
    NWS Heat Index calculation.
    """
    temp_f = temp_c * 1.8 + 32.0
    hi_f = 0.5 * (temp_f + 61.0 + ((temp_f - 68.0) * 1.2) + (rh * 0.094))
    if hi_f >= 80:
        hi_f = (-42.379 + 2.04901523 * temp_f + 10.14333127 * rh 
                - 0.22475541 * temp_f * rh - 6.83783 * (10**-3) * (temp_f**2)
                - 5.481717 * (10**-2) * (rh**2) + 1.22874 * (10**-3) * (temp_f**2) * rh
                + 8.5282 * (10**-4) * temp_f * (rh**2) - 1.99 * (10**-6) * (temp_f**2) * (rh**2))
    return round((hi_f - 32.0) / 1.8, 2)
