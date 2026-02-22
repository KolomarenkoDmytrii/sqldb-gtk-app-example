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

class OrderModel(gtk_data_model(models.Order)):
    @GObject.Property
    def product_name(self) -> str:
        "Read only property."
        sql_obj = self.to_sql_object()
        return sql_obj.product.name