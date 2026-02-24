# pylint: disable=wrong-import-position
"""Module for version of ListStore that syncs its stored objects with the database."""

from typing import Sequence, Generic, cast

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GObject

from .management import GtkT, SqlT, DataRepository, GtkDataModelProtocol


class ManagedListStore(Gio.ListStore, Generic[GtkT]):
    """
    A Gio.ListStore that integrates with DataRepository for
    automated UI/DB synchronization.
    """

    def __init__(self, item_type: type[GtkT], repository: DataRepository):
        """Create a ManagedListStore object.

        Args:
            item_type (type[GtkT]): the class of stored GObject view models.
            repository (DataRepository): data repository object for syncing with
                the database.
        """
        super().__init__(item_type=item_type)
        self.item_type = item_type
        self.repository = repository

    def save_items(self, items: Sequence[GtkDataModelProtocol]) -> None:
        """Saves passed GObject view models to the database.

        Args:
            items (Sequence[GtkDataModelProtocol]): sequence of GObject view models
                to be saved to the database.
        """
        self.repository.save(items)

        for item in items:
            # if the item isn't in the store yet (newly created), add it
            # cast() to GObject is used because ListStore expects GObjects
            g_item = cast(GObject.Object, item)
            found, _ = self.find(g_item)
            if not found:
                self.append(g_item)

    def delete_items(self, items: Sequence[GtkDataModelProtocol]) -> None:
        """Deletes passed GObject view models from the databse
        and removes them from the UI store.

        Args:
            items (Sequence[GtkDataModelProtocol]): Sequence of GObject view models
                to be saved to the database.
        """
        self.repository.delete(items)

        for item in items:
            g_item = cast(GObject.Object, item)
            # find the position of the item in the list
            found, index = self.find(g_item)
            if found:
                self.remove(index)

    def load_all(self, sql_cls: type[SqlT]) -> None:
        """Fetches everything from the database and populates the store.

        Args:
            sql_cls (type[SqlT]): Releted to `item_type` SQLAlchemy ORM class.
        """
        self.remove_all()
        db_items: Sequence[GtkT] = self.repository.fetch_all(sql_cls, self.item_type)
        self.splice(0, 0, [cast(GObject.Object, item) for item in db_items])
