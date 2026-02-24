# pylint: disable=wrong-import-position
"""The application entrypoint."""

import sys
from typing import Any, Self

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, event

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from support.widgets.main_window import MainWindow
from support.models import Base
from support.gtk_models.management import DataRepository


class App(Gtk.Application):
    """Class of the application."""

    def __init__(self, repository: DataRepository, **kwargs: Any) -> None:
        """Create a MainWindow object.

        Args:
            repository (DataRepository): A data repository for data syncronization and retrieval.
            **kwargs (Any): Additional arguments for `Gtk.Application`.
        """
        super().__init__(**kwargs)
        self.connect("activate", self.on_activate)
        self.repository = repository
        self.main_window: MainWindow | None = None

    def on_activate(self, app: Self) -> None:
        """Setup the application.

        Args:
            app (Self): The `App` object; not used.
        """
        self.main_window = MainWindow(repository=self.repository, application=app)
        self.main_window.set_default_size(1000, 700)
        self.main_window.present()


if __name__ == "__main__":
    # uncomment if data persistence is not needed
    # engine = create_engine("sqlite:///:memory:")
    engine = create_engine("sqlite:///data/data.db")

    # SQLite by default seems doesn't use cascade deletion, so force it
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _connection_record):
        """Force SQLite to use cascade deletion.""" 
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)
    data_repository = DataRepository(session)

    application = App(repository=data_repository, application_id="org.swarch.Lab5")
    application.run(sys.argv)
