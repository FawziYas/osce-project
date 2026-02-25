"""
Path naming utility – numeric naming (1, 2, 3, ...).
"""


def generate_path_name(index: int) -> str:
    """
    Generate a numeric path name for a given 0-based index.

    0 -> 1, 1 -> 2, 2 -> 3, etc.
    """
    return str(index + 1)
