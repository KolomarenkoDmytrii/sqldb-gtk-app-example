from typing import List, Type, Sequence, Generic, cast

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GObject

from .management import T_GTK, T_SQL, DataRepository, GtkDataModelProtocol


class ManagedListStore(Gio.ListStore, Generic[T_GTK]):
    """
    A Gio.ListStore that integrates with DataRepository for
    automated UI/DB synchronization.
    """

    def __init__(self, item_type: Type[T_GTK], repository: DataRepository):
        # In GTK 4, Gio.ListStore requires the GObject type it will hold
        super().__init__(item_type=item_type)
        self.item_type = item_type
        self.repository = repository

    def save_items(self, items: Sequence[GtkDataModelProtocol]) -> None:
        """Saves items to DB and ensures they are in the ListStore."""
        self.repository.save(items)

        for item in items:
            # If the item isn't in the store yet (newly created), add it
            # We use cast to GObject because ListStore expects GObjects
            g_item = cast(GObject.Object, item)
            found, _ = self.find(g_item)
            if not found:
                self.append(g_item)

    def delete_items(self, items: Sequence[GtkDataModelProtocol]) -> None:
        """Deletes items from DB and removes them from the UI Store."""
        self.repository.delete(items)

        for item in items:
            g_item = cast(GObject.Object, item)
            # Find the position of the item in the list
            found, index = self.find(g_item)
            if found:
                self.remove(index)

    def load_all(self, sql_cls: Type[T_SQL]) -> None:
        """Fetches everything from DB and populates the store."""
        self.remove_all()
        # You'd add a 'fetch_all' method to your Repository
        # that returns GtkDataModels
        # db_items: Sequence[T_GTK] = self.repository.fetch_all(sql_cls, self.get_item_type())
        db_items: Sequence[T_GTK] = self.repository.fetch_all(sql_cls, self.item_type)
        self.splice(0, 0, [cast(GObject.Object, item) for item in db_items])

    # def get_all(self) -> Sequence[T_GTK]:
    #     return [cast(T_GTK, self.get_item(i)) for i in range(self.get_n_items())]

        # for item in db_items:
        #     self.append(cast(GObject.Object, item))
