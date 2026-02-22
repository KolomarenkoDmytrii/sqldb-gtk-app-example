from typing import List, Type, TypeVar, Iterable, Any, Sequence, cast

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, GObject

from .gtk_models.management import T_GTK, T_SQL, DataRepository, GtkDataModelProtocol
from .gtk_models.models_store import ManagedListStore


class DatabaseTableWidget(Gtk.Box):
    """
    A reusable GTK 4 widget that provides a table view for a SQLAlchemy model,
    including Add, Delete, and Save functionality.
    """

    def __init__(
        self,
        sql_cls: Type[T_SQL],
        gtk_model_cls: Type[T_GTK],
        repository: DataRepository,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10, hexpand=True, vexpand=True)

        self.sql_cls = sql_cls
        self.gtk_model_cls = gtk_model_cls
        self.repository = repository

        # 1. Initialize Data Storage
        self.list_store = ManagedListStore(
            item_type=gtk_model_cls, repository=repository
        )
        self.selection_model = Gtk.MultiSelection.new(self.list_store)
        # Track unique changed items by ID/Hash
        self.changed_items: dict[int, T_GTK] = {}

        # 2. Build UI Components
        self._build_toolbar()
        self._build_view()

        # 3. Load Initial Data
        self.list_store.load_all(self.sql_cls)

    def _build_toolbar(self):
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        add_btn = Gtk.Button(label="Add Row")
        add_btn.connect("clicked", self._on_add_clicked)

        delete_btn = Gtk.Button(label="Delete Selected")
        delete_btn.connect("clicked", self._on_delete_clicked)

        save_btn = Gtk.Button(label="Save Changes")
        save_btn.set_css_classes(["suggested-action"])
        save_btn.connect("clicked", self._on_save_clicked)

        toolbar.append(add_btn)
        toolbar.append(delete_btn)
        toolbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        toolbar.append(save_btn)

        self.append(toolbar)

    def _build_view(self):
        self.column_view = Gtk.ColumnView(model=self.selection_model)
        self.column_view.set_vexpand(True)

        # Automatically generate columns based on GObject properties
        # (Excluding internal GTK properties and 'is_deleted')
        dummy_instance = self.gtk_model_cls()
        for prop in dummy_instance.list_properties():
            if prop.name in ["is-deleted", "is_deleted"] or prop.name.startswith("gtk"):
                continue

            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", self._on_factory_setup)
            factory.connect("bind", self._on_factory_bind, prop.name)

            column = Gtk.ColumnViewColumn(title=prop.name.title(), factory=factory)
            self.column_view.append_column(column)

        # Wrap in ScrolledWindow
        sw = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        sw.set_child(self.column_view)
        self.append(sw)

    # --- Factory Logic ---

    def _on_factory_setup(self, factory, list_item):
        label = Gtk.EditableLabel()
        list_item.set_child(label)

    def _on_factory_bind(self, factory, list_item, prop_name):
        model_obj = list_item.get_item()
        editable_label = cast(Gtk.EditableLabel, list_item.get_child())

        # Bind the GObject property to the label text
        model_obj.bind_property(
            prop_name,
            editable_label,
            "text",
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )

        # Track changes when the user stops editing
        editable_label.connect("notify::editing", self._on_cell_edited, model_obj)

    def _on_cell_edited(self, label, pspec, model_obj):
        if not label.get_editing():
            # Use object hash as key to avoid duplicates in change tracking
            self.changed_items[hash(model_obj)] = model_obj

    # --- Action Handlers ---

    def _on_add_clicked(self, btn):
        """Insert a new empty row at the bottom [Remark 2]."""
        new_row = self.gtk_model_cls()
        self.list_store.append(new_row)
        self.changed_items[hash(new_row)] = new_row

    def _on_delete_clicked(self, btn):
        """Delete rows selected by the user [Remark 1]."""
        selection = self.selection_model.get_selection()
        if selection.is_empty():
            return

        to_delete = []
        # Bitset iteration to find selected items
        for i in range(self.list_store.get_n_items()):
            if selection.contains(i):
                to_delete.append(self.list_store.get_item(i))

        self.list_store.delete_items(to_delete)
        # Remove deleted items from the pending save list
        for item in to_delete:
            self.changed_items.pop(hash(item), None)

    def _on_save_clicked(self, btn):
        """Persist tracked changes to the database."""
        if not self.changed_items:
            return

        self.list_store.save_items(list(self.changed_items.values()))
        self.changed_items.clear()
