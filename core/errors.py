class DuplicateFileError(Exception):
    def __init__(self, original: str, duplicate: str):
        self.original = original
        self.duplicate = duplicate
        super().__init__(f"Duplicate detected: {original} vs {duplicate}")
