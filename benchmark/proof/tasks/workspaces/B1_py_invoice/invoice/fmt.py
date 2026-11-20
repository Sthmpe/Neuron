def naira(kobo):
    """Format kobo as naira with two decimals, e.g. 2150000 -> 'NGN 21,500.00'."""
    return f"NGN {kobo / 100:,.2f}"
