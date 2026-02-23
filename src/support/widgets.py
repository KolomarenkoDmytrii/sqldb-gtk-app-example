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
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL, spacing=10, hexpand=True, vexpand=True
        )

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

        # Subscribe to repository changes
        self.repository.subscribe_to_changes(self._on_db_changed)

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
        fk_configs = getattr(self.gtk_model_cls, "_fk_configs", {})
        print(fk_configs)
        print(dummy_instance.list_properties())
        for prop in dummy_instance.list_properties():
            if prop.name in ["is-deleted", "is_deleted"] or prop.name.startswith("gtk"):
                continue

            factory = Gtk.SignalListItemFactory()
            # Use a DropDown for FKs, otherwise use EditableLabel
            print(f"{self.sql_cls.__name__} | prop.name='{prop.name}'")
            # if prop.name in fk_configs:
            if "_".join(prop.name.split("-")) in fk_configs:
                print("dropdown!")
                factory.connect("setup", self._on_dropdown_factory_setup)
                factory.connect("bind", self._on_dropdown_factory_bind, "_".join(prop.name.split("-")))
            else:
                factory.connect("setup", self._on_factory_setup)
                factory.connect("bind", self._on_factory_bind, prop.name)

            column = Gtk.ColumnViewColumn(title=prop.name.title(), factory=factory)
            self.column_view.append_column(column)

        # Wrap in ScrolledWindow
        sw = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        sw.set_child(self.column_view)
        self.append(sw)
        print("-----")

    # --- Factory Logic ---

    def _on_factory_setup(self, factory, list_item):
        label = Gtk.EditableLabel()
        list_item.set_child(label)

    def _on_factory_bind(self, factory, list_item, prop_name):
        model_obj = list_item.get_item()
        editable_label = cast(Gtk.EditableLabel, list_item.get_child())

        # # Bind the GObject property to the label text
        # model_obj.bind_property(
        #     prop_name,
        #     editable_label,
        #     "text",
        #     GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        # )
        # Add bidirectional transform functions
        model_obj.bind_property(
            prop_name,
            editable_label,
            "text",
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
            lambda b, val: str(val) if val is not None else "",  # To UI
            lambda b, val: self._string_to_type(val, prop_name),  # From UI
        )

        # Track changes when the user stops editing
        editable_label.connect("notify::editing", self._on_cell_edited, model_obj)

    def _on_cell_edited(self, label, pspec, model_obj):
        if not label.get_editing():
            # Use object hash as key to avoid duplicates in change tracking
            self.changed_items[hash(model_obj)] = model_obj

    def _on_dropdown_factory_setup(self, factory, list_item):
        # We use a DropDown instead of an EditableLabel
        dropdown = Gtk.DropDown()
        list_item.set_child(dropdown)

    def _on_dropdown_factory_bind(self, factory, list_item, prop_name):
        model_obj = list_item.get_item()
        dropdown = cast(Gtk.DropDown, list_item.get_child())

        # Get the target SQL class from our metadata
        target_sql_cls = getattr(self.gtk_model_cls, "_fk_configs", {}).get(prop_name)
        if not target_sql_cls:
            return

        # Fetch options
        with self.repository.session_factory() as session:
            results = session.query(target_sql_cls).all()
            # Try to find a 'name' attribute, fallback to ID
            choices = [
                str(getattr(r, "name", getattr(r, "id", "???"))) for r in results
            ]
            ids = [getattr(r, "id") for r in results]

        # Crucial: Use a Gtk.StringList and set it to the dropdown
        string_list = Gtk.StringList.new(choices)
        dropdown.set_model(string_list)

        # Set the current selection without triggering the signal
        current_val = getattr(model_obj, prop_name)
        if current_val in ids:
            dropdown.set_selected(ids.index(current_val))

        # Re-connect the signal for user changes
        # Use a unique handler ID to prevent recursive calls during binding
        handler_id = dropdown.connect(
            "notify::selected", self._on_dropdown_changed, model_obj, prop_name, ids
        )
        # Store handler_id if needed for unbinding, or just handle in the callback

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

    def _on_dropdown_changed(self, dropdown, pspec, model_obj, prop_name, ids):
        selected_idx = dropdown.get_selected()
        new_id = ids[selected_idx]
        print(f"{self.sql_cls.__name__} | '{selected_idx}' : new_id")
        setattr(model_obj, prop_name, new_id)
        self.changed_items[hash(model_obj)] = model_obj

    def _on_db_changed(self, changed_sql_cls: type):
        """Called whenever any table in the DB is saved/deleted."""
        fk_configs = getattr(self.gtk_model_cls, "_fk_configs", {})
        
        # Check if the changed table is one we rely on for a DropDown
        if changed_sql_cls in fk_configs.values():
            print(f"Refreshing table {self.sql_cls.__name__} because {changed_sql_cls.__name__} updated.")
            
            # This forces the ColumnView to re-bind all rows, 
            # which re-runs the DropDown population logic.
            # A simple way is to 'fake' a change in the selection model
            # or just refresh the whole store if you want to be safe:
            self.list_store.load_all(self.sql_cls)

    def _string_to_type(self, value: str, prop_name: str) -> Any:
        """Helper to cast string back to the GObject property type."""
        prop = self.gtk_model_cls.find_property(prop_name)
        if prop.value_type == GObject.TYPE_INT:
            return int(value) if value.isdigit() else 0
        if prop.value_type == GObject.TYPE_DOUBLE or prop.value_type == GObject.TYPE_FLOAT:
            try: return float(value)
            except: return 0.0
        return value