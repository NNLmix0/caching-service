def transform(value: str) -> str:
    """Stand-in for a slow external service; its results are what gets cached."""
    return value.upper()
