export type BookType =
  | "fiction"
  | "non_fiction"
  | "biography"
  | "science"
  | "history"
  | "poetry"
  | "other";

export interface Author {
  id: string;
  first_name: string;
  last_name: string;
  bio: string | null;
}

export interface CreateAuthor {
  first_name: string;
  last_name: string;
  bio?: string | null;
}

export interface UpdateAuthor {
  first_name?: string;
  last_name?: string;
  bio?: string | null;
}

export interface AuthorList {
  items: Author[];
  total_count: number;
}

export interface Book {
  id: string;
  title: string;
  author_id: string;
  book_type: BookType;
  isbn: string | null;
  published_year: number | null;
}

export interface CreateBook {
  title: string;
  author_id: string;
  book_type?: BookType;
  isbn?: string | null;
  published_year?: number | null;
}

export interface UpdateBook {
  title?: string;
  book_type?: BookType;
  isbn?: string | null;
  published_year?: number | null;
}

export interface BookList {
  items: Book[];
  total_count: number;
}
