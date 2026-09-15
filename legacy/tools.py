def write_py_file(file_path: str, content: str):
    """
    Write a string into a .py file (overwrites if exists).

    file path should have underscrore between seperate words.

    always write files to a folder called 'generated

    use proper intendations when writing strings to python files. The strings should be written as code block.

    Args:
        file_path (str): Destination path.
        content (str): Text to write.
    Returns:
        str: Path to the written file.
    """
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return file_path