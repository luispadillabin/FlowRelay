# Understand your project

Begin with `validate()` in relay.py, then follow `submit()`, `process()`, and
handler_for() in server.py. Trace one event from the Send button in app.js to the
HTTP handler, database insert, processing transaction, and inspector response.

## Explain these decisions

- Why does a repeated request return 200 but a changed payload with the same ID return 409?
- Why is an event ID a better deduplication key than its summary?
- Why must checking the ID and inserting the row happen in one transaction?
- Why do retries wait instead of looping immediately?
- Why does this simulator's transaction not guarantee exactly-once external delivery?
- Why is a loopback learning server different from a production webhook receiver?

## First independent improvement

Add a fourth scenario button that fails twice, then succeeds. Before editing,
predict the states and due times. Write a queue test for fail_until=2, then make
the UI change and test it locally. Use a Git branch and explain the change in
your commit or pull request.

## Interview explanation

Describe it as a local webhook-processing simulator. Mention validation,
idempotent submission, transactional state changes, bounded retries, SQLite
persistence and automated tests. Be clear that it does not send actual webhooks,
and acknowledge AI assistance accurately when asked about development.
