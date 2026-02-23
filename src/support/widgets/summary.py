from sqlalchemy import func, select

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, GObject

from ..gtk_models.management import DataRepository, T_SQL, T_GTK, GtkDataModelProtocol
from ..gtk_models.models_store import ManagedListStore
from ..gtk_models.models import ProductModel
from ..models import Order


class SummaryWidget(Gtk.Box):
    def __init__(self, models_store: ManagedListStore, repository: DataRepository):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10, hexpand=True)

        self.models_store = models_store
        self.repository = repository

        if self.models_store.item_type != ProductModel:
            raise ValueError(
                f"models_store must contain ProductModel objects, given {models_store.item_type.__name__}"
            )

        self._product_lefts_list = Gtk.ListBox()
        self._product_lefts_list.bind_model(
            model=self.models_store, create_widget_func=self._create_label
        )

        self.append(self._product_lefts_list)

        # SUBSCRIBE to changes: 
        # Whenever ANY table changes (Products OR Orders), we must refresh these labels.
        self.repository.subscribe_to_changes(self._on_data_changed)

    def _on_data_changed(self, changed_sql_cls: type[T_SQL]):
        # We don't care which table changed; both affect the calculation
        # invalidate_filter() or simply notifying the store 
        # forces the 'create_widget_func' to run again for all rows.
        self.models_store.items_changed(0, self.models_store.get_n_items(), self.models_store.get_n_items())

    def _create_label(self, gtk_model: GtkDataModelProtocol) -> Gtk.Label:
        product = gtk_model.to_sql_object()
        # orders_total = sum(order.quantity for order in obj.orders) # not works
        # Manually calculate sum from DB to ensure accuracy 
        # (avoiding stale lazy-loaded 'obj.orders' collections)
        with self.repository.session_factory() as session:
            # Query the sum of quantities for this product
            stmt = select(func.sum(Order.quantity)).where(Order.product_id == product.id)
            orders_total = session.scalar(stmt) or 0

        lefts = product.quantity - orders_total

        label_string: str = ""
        if lefts < 0:
            label_string = f"Need to supply of {product.name}: {-lefts}"
        else:
            label_string = f"Left of {product.name}: {lefts}"

        return Gtk.Label.new(label_string)
