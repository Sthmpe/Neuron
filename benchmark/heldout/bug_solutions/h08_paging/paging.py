"""Split a list into pages."""


def total_pages(item_count, page_size):
    """How many pages are needed to show every item."""
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    return (item_count + page_size - 1) // page_size


def page(items, number, page_size):
    """Items on page `number` (the first page is 1)."""
    if number < 1:
        raise ValueError("pages start at 1")
    start = (number - 1) * page_size
    return items[start:start + page_size]


def has_next(item_count, number, page_size):
    return number < total_pages(item_count, page_size)
