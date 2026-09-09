class AuthorNotFoundError(Exception):
    def __init__(self, author_id):
        super().__init__(f"Author {author_id} not found")
