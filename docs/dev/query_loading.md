# Query Loading Best Practices

To avoid N+1 query regressions when working with documents and their passages,
follow these guidelines:

1. **Always choose an eager loading strategy.**
   Use SQLAlchemy's [`selectinload`](https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html#sqlalchemy.orm.selectinload)
   (or another appropriate eager option) whenever you know the caller will need
   related objects such as `Document.passages` or `Document.annotations`.
   Apply the option directly to the `select()` statement or query helper rather
   than relying on implicit lazy loading.

2. **Prefer explicit `select()` statements.**
   Fetch models with `session.scalars(select(Model).options(...))` so the eager
   loader is applied consistently across repository and service layers. Avoid
   `session.get()` when relationship options are required.

3. **Verify with query-count tests.**
   Add regression tests that record SQL statements for representative workflows.
   Assert that document retrieval executes a bounded number of `SELECT`
   statements even when multiple passages are present. This prevents future
   changes from reintroducing N+1 behaviour.

4. **Access relationships inside the monitored context.**
   In tests, access `document.passages` (or the relevant relationship) while the
   SQL recorder is active. This ensures that deferred lazy loads would be
   detected by the assertions.

5. **Document expectations in code reviews.**
   Mention the expected query plan (for example, "one query for documents, one
   for passages via `selectinload`") so reviewers can confirm the eager loading
   strategy remains intact.

Following these practices keeps document retrieval predictable and efficient as
new services or repositories evolve.
