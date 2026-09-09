class BookNotFoundError(Exception):
    def __init__(self, book_id):
        super().__init__(f"Book {book_id} not found")
