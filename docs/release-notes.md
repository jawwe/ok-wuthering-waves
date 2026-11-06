AsterDesk 1.0.1 independent portable distribution.

Fix the connection button raising `TypeError: 'type' object is not iterable`.
The global input backend is now registered as a list, compatible with both the
runtime and connection panel. Portable self-checks cover the connection options.

- Restored Character Code and team workshop pages.
- Bundled complete workshop catalog and code archives, with durable offline cache.
- Added global keyboard/mouse backend switching and configuration import.
- Isolated application data and the independent release channel.
- Neutral launcher, worker process, window title and icon.

Extract the whole portable folder. Preserve `data/` when updating.
