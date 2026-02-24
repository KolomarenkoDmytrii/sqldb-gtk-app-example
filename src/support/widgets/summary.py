# pylint: disable=wrong-import-position
"""A module that contains widget for the products lefts summary."""

from sqlalchemy import func, select

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ..gtk_models.management import DataRepository, SqlT
from ..gtk_models.models_store import ManagedListStore
from ..gtk_models.models import ProductModel
from ..models import Order


class SummaryWidget(Gtk.Box):
    """Widget with the lefts info for every product."""

    def __init__(
        self, models_store: ManagedListStore, repository: DataRepository
    ) -> None:
        """Create a SummaryWidget object.

        Args:
            models_store (ManagedListStore): A `ManagedListStore` for `ProductModel` view models.
            repository (DataRepository): A data repository which is used for data retrieval.
        """
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10, vexpand=True)

        self.models_store = models_store
        self.repository = repository

        if self.models_store.item_type != ProductModel:
            raise ValueError(
                "models_store must contain ProductModel objects, "
                + f"given {models_store.item_type.__name__}"
            )

        self._product_lefts_list = Gtk.ListBox()
        self._product_lefts_list.bind_model(
            model=self.models_store, create_widget_func=self._create_label
        )

        self.append(self._product_lefts_list)

        # subscribe to changes:
        # whenever any table changes (Products or Orders), labels must be refreshed
        self.repository.subscribe_to_changes(self._on_data_changed)

    def _on_data_changed(self, _changed_sql_cls: type[SqlT]) -> None:
        """Handle changes in tables and update labels correspondingly.

        Args:
            _changed_sql_cls (type[SqlT]): dummy parameter.
        """
        # emit 'items-changed' signal if any table is updated
        self.models_store.items_changed(
            0, self.models_store.get_n_items(), self.models_store.get_n_items()
        )

    def _create_label(self, gtk_model: ProductModel) -> Gtk.Label:
        """Create label for the product lefts info.

        Args:
            gtk_model (ProductModel): A view model of the product which info
                about lefts will be displayed.

        Returns:
            Gtk.Label: A label with the product lefts info.
        """
        product = gtk_model.to_sql_object()
        # manually calculate sum from DB to ensure accuracy
        # (avoiding stale lazy-loaded 'obj.orders' collections)
        with self.repository.session_factory() as session:
            # Query the sum of quantities for this product
            stmt = select(func.sum(Order.quantity)).where(
                Order.product_id == product.id
            )
            orders_total = session.scalar(stmt) or 0

        lefts = product.quantity - orders_total

        label_string: str = ""
        if lefts < 0:
            label_string = f"Need to supply of {product.name}: {-lefts}"
        else:
            label_string = f"Left of {product.name}: {lefts}"

        return Gtk.Label.new(label_string)
