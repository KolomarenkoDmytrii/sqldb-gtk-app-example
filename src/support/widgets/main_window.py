import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .. import models
from ..gtk_models.models import ProductModel, OrderModel
from ..gtk_models.management import DataRepository
from .db_table import DatabaseTableWidget
from .summary import SummaryWidget


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, repository: DataRepository, **kargs):
        super().__init__(**kargs, title="Product Management")
        notebook = Gtk.Notebook()
        products_table = DatabaseTableWidget(models.Product, ProductModel, repository)
        orders_table = DatabaseTableWidget(models.Order, OrderModel, repository)
        
        summary = SummaryWidget(products_table.list_store, repository)

        notebook.append_page(products_table, Gtk.Label.new("Products"))
        notebook.append_page(orders_table, Gtk.Label.new("Orders"))
        notebook.append_page(summary, Gtk.Label.new("Lefts"))
        self.set_child(notebook)