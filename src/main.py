from typing import Callable
import sys

from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine, event

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from support import models
from support.gtk_models.models import ProductModel, OrderModel
from support.gtk_models.management import DataRepository
from support.widgets.db_table import DatabaseTableWidget


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, repository: DataRepository, **kargs):
        super().__init__(**kargs, title="Product Management")
        # box = Gtk.Box(spacing=4, orientation=Gtk.Orientation.VERTICAL)
        notebook = Gtk.Notebook()
        products_table = DatabaseTableWidget(models.Product, ProductModel, repository)
        orders_table = DatabaseTableWidget(models.Order, OrderModel, repository)
        notebook.append_page(products_table, Gtk.Label.new("Products"))
        notebook.append_page(orders_table, Gtk.Label.new("Orders"))
        # box.append(table)
        # self.set_child(box)
        self.set_child(notebook)


class App(Gtk.Application):
    def __init__(self, repository: DataRepository, **kwargs):
        super().__init__(**kwargs)
        self.connect("activate", self.on_activate)
        self.repository = repository

    # Метод який вказує, що виконати при активації застосунку
    def on_activate(self, app):
        self.main_window = MainWindow(repository=self.repository, application=app)
        self.main_window.set_default_size(900, 450)
        self.main_window.present()


if __name__ == "__main__":
    # engine = create_engine("sqlite:///:memory:")
    engine = create_engine("sqlite:///data/data.db")
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    models.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)
    data_repository = DataRepository(session)

    app = App(repository=data_repository, application_id="org.swarch.Lab5")
    app.run(sys.argv)
