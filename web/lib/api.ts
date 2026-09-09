import type {
  Author,
  AuthorList,
  Book,
  BookList,
  CreateAuthor,
  CreateBook,
  UpdateAuthor,
  UpdateBook,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8010";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail ?? res.statusText);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  authors: {
    list: () => request<AuthorList>("/authors"),
    get: (id: string) => request<Author>(`/authors/${id}`),
    create: (data: CreateAuthor) =>
      request<Author>("/authors", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: UpdateAuthor) =>
      request<Author>(`/authors/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (id: string) => request<void>(`/authors/${id}`, { method: "DELETE" }),
  },
  books: {
    list: (authorId?: string) =>
      request<BookList>(`/books${authorId ? `?author_id=${authorId}` : ""}`),
    get: (id: string) => request<Book>(`/books/${id}`),
    create: (data: CreateBook) =>
      request<Book>("/books", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: UpdateBook) =>
      request<Book>(`/books/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (id: string) => request<void>(`/books/${id}`, { method: "DELETE" }),
  },
};

export { ApiError };
