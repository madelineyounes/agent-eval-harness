def paginate(items, page_size):
    return [
        items[start:start + page_size]
        for start in range(0, len(items) + 1, page_size)
    ]
