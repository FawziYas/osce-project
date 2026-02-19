"""
Path naming utility – Excel-style column naming (A, B, ..., Z, AA, AB, ...).
"""


def generate_path_name(index: int) -> str:
    """
    Generate an Excel-style column name for a given 0-based index.

    0 -> A, 1 -> B, ... 25 -> Z, 26 -> AA, 27 -> AB, etc.
    """
    name = ''
    index += 1  # 1-based
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name
