import { api } from "@/lib/api";

export default async function Home() {
  const [authors, books] = await Promise.all([
    api.authors.list().catch(() => ({ items: [], total_count: 0 })),
    api.books.list().catch(() => ({ items: [], total_count: 0 })),
  ]);

  return (
    <div className="min-h-screen bg-zinc-50 px-6 py-16 font-sans dark:bg-black">
      <main className="mx-auto flex w-full max-w-3xl flex-col gap-10">
        <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
          Library
        </h1>

        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-medium text-black dark:text-zinc-50">
            Authors ({authors.total_count})
          </h2>
          {authors.items.length === 0 ? (
            <p className="text-sm text-zinc-500">
              No authors yet — create one via the API.
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {authors.items.map((author) => (
                <li
                  key={author.id}
                  className="rounded border border-zinc-200 px-4 py-3 text-sm dark:border-zinc-800"
                >
                  <span className="font-medium">
                    {author.first_name} {author.last_name}
                  </span>
                  {author.bio && (
                    <span className="text-zinc-500"> — {author.bio}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-medium text-black dark:text-zinc-50">
            Books ({books.total_count})
          </h2>
          {books.items.length === 0 ? (
            <p className="text-sm text-zinc-500">
              No books yet — create one via the API.
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {books.items.map((book) => (
                <li
                  key={book.id}
                  className="rounded border border-zinc-200 px-4 py-3 text-sm dark:border-zinc-800"
                >
                  <span className="font-medium">{book.title}</span>
                  <span className="text-zinc-500">
                    {" "}
                    ({book.book_type}
                    {book.published_year ? `, ${book.published_year}` : ""})
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}
