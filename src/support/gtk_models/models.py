import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GObject

from .. import models
from .management import gtk_data_model

# # ProductModel inherits from the dynamic class and satisfies GtkDataModelProtocol
# class ProductModel(gtk_data_model(models.Product)): # type: ignore[misc, valid-type]
# # class ProductModel(cast(Any, gtk_data_model(Product))):
#     is_dirty = GObject.Property(type=bool, default=False)

ProductModel = gtk_data_model(models.Product)
