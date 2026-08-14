"""
Shared test configuration.

Neutralizes Django's ``close_old_connections`` signal handlers.

Django connects ``close_old_connections`` to ``request_started`` and
``request_finished`` at import time. With the file-based SQLite test
database (see config/settings/test.py) that signal actually closes the
connection — unlike in-memory SQLite, where Django ignores ``close()``.
A streaming response (FileResponse) defers ``request_finished`` until
``response.close()``, so tests that close such a response and then keep
querying blow up with "Cannot operate on a closed database".

Tests don't need connection recycling — pytest-django manages the
connection lifecycle per test — so disconnect the real receiver and point
the module attribute at a no-op. The attribute swap matters because
``django.test.client`` imports ``close_old_connections`` lazily and
disconnects/reconnects it around streaming responses; with the no-op in
place it can never resurrect the real handler.
"""

import django.db
from django.core import signals

_original_close_old_connections = django.db.close_old_connections

signals.request_started.disconnect(_original_close_old_connections)
signals.request_finished.disconnect(_original_close_old_connections)


def _keep_connections(**kwargs):  # noqa: ARG001 - signal receiver signature
    """Never recycle connections during tests."""


django.db.close_old_connections = _keep_connections
