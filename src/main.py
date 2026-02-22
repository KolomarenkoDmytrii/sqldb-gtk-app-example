from typing import Callable
import sys

from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from support import models
from support.gtk_models.models import ProductModel
from support.gtk_models.management import DataRepository
from support.widgets import DatabaseTableWidget


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, repository: DataRepository, **kargs):
        super().__init__(**kargs, title="Lab 5")
        box = Gtk.Box(spacing=4, orientation=Gtk.Orientation.VERTICAL)
        table = DatabaseTableWidget(models.Product, ProductModel, repository)
        box.append(table)
        self.set_child(box)


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
    models.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)
    data_repository = DataRepository(session)

    app = App(repository=data_repository, application_id="org.swarch.Lab5")
    app.run(sys.argv)
