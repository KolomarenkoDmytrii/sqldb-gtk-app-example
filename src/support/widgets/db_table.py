# pylint: disable=wrong-import-position
"""A module that contains widget for the database table editing."""

from typing import Sequence, Generic, Any, cast

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject

from ..gtk_models.management import GtkT, SqlT, DataRepository
from ..gtk_models.models_store import ManagedListStore


class DatabaseTableWidget(Gtk.Box, Generic[GtkT]):
    """A reusable GTK 4 widget that provides a table view for a SQLAlchemy model,
    including add, delete and save functionality.
    """

    def __init__(
        self,
        sql_cls: type[SqlT],
        gtk_model_cls: type[GtkT],
        repository: DataRepository,
    ) -> None:
        """Create a DatabaseTableWidget object.

        Args:
            sql_cls (type[SqlT]): A SQLAlchemy ORM class which data will be displayed.
            gtk_model_cls (type[GtkT]): A related to `sql_cls` GObject view model.
            repository (DataRepository): A data repository which is used to sync changes
                with the database.
        """
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL, spacing=10, hexpand=True, vexpand=True
        )

        self.sql_cls = sql_cls
        self.gtk_model_cls = gtk_model_cls
        self.repository = repository

        # initialize Data Storage
        self.list_store = ManagedListStore(
            item_type=gtk_model_cls, repository=repository
        )
        self.selection_model = Gtk.MultiSelection.new(self.list_store)
        # track unique changed items by ID/Hash
        self.changed_items: dict[int, GtkT] = {}

        # build UI components
        self._build_toolbar()
        self._build_view()

        # load initial data
        self.list_store.load_all(self.sql_cls)

        # subscribe to repository changes
        self.repository.subscribe_to_changes(self._on_db_changed)

    def _build_toolbar(self):
        """Build the toolbar of table widget."""
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
        """Build the table of a widget."""
        self.column_view = Gtk.ColumnView(model=self.selection_model)
        self.column_view.set_vexpand(True)

        # automatically generate columns based on GObject properties
        dummy_instance = self.gtk_model_cls()
        fk_configs = getattr(self.gtk_model_cls, "_fk_configs", {})
        for prop in dummy_instance.list_properties():
            # exclude internal GTK and private properties
            if prop.name.startswith("gtk") or prop.name.startswith("_"):
                continue

            factory = Gtk.SignalListItemFactory()

            # GObject properties has '-' instead of '_' in their introspection names,
            # so replace '-' with '_' instead
            if (
                "_".join(prop.name.split("-")) in fk_configs
            ):  # use a DropDown for foreign keys
                factory.connect("setup", self._on_dropdown_factory_setup)
                factory.connect(
                    "bind",
                    self._on_dropdown_factory_bind,
                    "_".join(prop.name.split("-")),
                )
            else:  # otherwise use EditableLabel
                factory.connect("setup", self._on_factory_setup)
                factory.connect("bind", self._on_factory_bind, prop.name)

            column = Gtk.ColumnViewColumn(title=prop.name.title(), factory=factory)
            self.column_view.append_column(column)

        # wrap the table in ScrolledWindow for scrolling
        sw = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        sw.set_child(self.column_view)
        self.append(sw)

    # --- Factory Logic ---

    def _on_factory_setup(
        self, _factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell
    ) -> None:
        """Setup table cell for view model property.

        Args:
            _factory (Gtk.SignalListItemFactory): The factory for creating collumns; not used.
            list_item (Gtk.ColumnViewCell): A cell of the table.
        """
        label = Gtk.EditableLabel()
        list_item.set_child(label)

    def _on_factory_bind(
        self,
        _factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ColumnViewCell,
        prop_name: str,
    ) -> None:
        """Setup a table cell for the view model property.

        Args:
            _factory (Gtk.SignalListItemFactory): The factory for creating collumns; not used.
            list_item (Gtk.ColumnViewCell): a cell of the table.
            prop_name (str): the name of the property which will be displayed
                in the respected table column.
        """
        model_obj = cast(GObject.GObject, list_item.get_item())
        editable_label = cast(Gtk.EditableLabel, list_item.get_child())

        # add bidirectional transform functions
        model_obj.bind_property(
            prop_name,
            editable_label,
            "text",
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
            lambda b, val: str(val) if val is not None else "",  # To UI
            lambda b, val: self._string_to_type(val, prop_name),  # From UI
        )

        # track changes when the user stops editing
        editable_label.connect("notify::editing", self._on_cell_edited, model_obj)

    def _on_dropdown_factory_setup(
        self, _factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell
    ):
        """Setup a table cell with a dropdown for the view model property
        which is related to the foreign key.

        Args:
            _factory (Gtk.SignalListItemFactory): The factory for creating collumns; not used.
            list_item (Gtk.ColumnViewCell): A cell of the table.
        """
        dropdown = Gtk.DropDown()
        list_item.set_child(dropdown)

    def _on_dropdown_factory_bind(
        self,
        _factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ColumnViewCell,
        prop_name: str,
    ) -> None:
        """Setup a table cell with dropdoen for the view model property
        which is related to the foreign key.

        Args:
            _factory (Gtk.SignalListItemFactory): The factory for creating collumns; not used.
            list_item (Gtk.ColumnViewCell): a cell of the table.
            prop_name (str): the name of the property which will be displayed
                in the respected table column.
        """
        model_obj = list_item.get_item()
        dropdown = cast(Gtk.DropDown, list_item.get_child())

        # get the target SQLAlchemy ORM class from the view model metadata
        target_sql_cls = getattr(self.gtk_model_cls, "_fk_configs", {}).get(prop_name)
        if not target_sql_cls:
            return

        # fetch options
        with self.repository.session_factory() as session:
            results = session.query(target_sql_cls).all()
            # try to find a 'name' attribute, fallback to 'id'
            choices = [
                str(getattr(r, "name", getattr(r, "id", "???"))) for r in results
            ]
            ids = [getattr(r, "id") for r in results]

        string_list = Gtk.StringList.new(choices)
        dropdown.set_model(string_list)

        # set the current selection without triggering the signal
        current_val = getattr(model_obj, prop_name)
        if current_val in ids:
            dropdown.set_selected(ids.index(current_val))

        dropdown.connect(
            "notify::selected", self._on_dropdown_changed, model_obj, prop_name, ids
        )

    # --- Action Handlers ---

    def _on_add_clicked(self, _btn: Gtk.Button) -> None:
        """Insert a new empty row at the bottom.

        Args:
            _btn (Gtk.Button): a button that emited `clicked` signal; not used.
        """
        new_row = self.gtk_model_cls()
        self.list_store.append(cast(GObject.GObject, new_row))
        self.changed_items[hash(new_row)] = new_row

    def _on_delete_clicked(self, _btn: Gtk.Button) -> None:
        """Delete rows selected by the user.

        Args:
            _btn (Gtk.Button): a button that emited `clicked` signal; not used.
        """
        selection = self.selection_model.get_selection()
        if selection.is_empty():
            return

        to_delete: list[GtkT] = []
        # bitset iteration to find selected items
        for i in range(self.list_store.get_n_items()):
            if selection.contains(i):
                to_delete.append(cast(GtkT, self.list_store.get_item(i)))

        self.list_store.delete_items(to_delete)
        # remove deleted items from the pending save list
        for item in to_delete:
            self.changed_items.pop(hash(item), None)

    def _on_save_clicked(self, _btn: Gtk.Button) -> None:
        """Persist tracked changes to the database.

        Args:
            _btn (Gtk.Button): a button that emited `clicked` signal; not used.
        """
        if not self.changed_items:
            return

        self.list_store.save_items(list(self.changed_items.values()))
        self.changed_items.clear()

    def _on_cell_edited(
        self,
        label: Gtk.EditableLabel,
        _pspec: GObject.ParamSpec,
        model_obj: GtkT,
    ) -> None:
        """Handle cell editing.

        Args:
            label (Gtk.EditableLabel): A label which content was edited.
            _pspec (GObject.ParamSpec): Encapsulates the metadata required to specify parameters,
                such as GObject properties; not used.
            model_obj (GtkT): changed GObject view model.
        """
        if not label.get_editing():
            # object hash is used as a key to avoid duplicates in change tracking
            self.changed_items[hash(model_obj)] = model_obj

    # pylint: disable=too-many-arguments
    def _on_dropdown_changed(
        self,
        dropdown: Gtk.DropDown,
        _pspec: GObject.ParamSpec,
        model_obj: GtkT,
        prop_name: str,
        ids: Sequence[int],
    ) -> None:
        """Handler of the dropdown value change.

        Args:
            dropdown (Gtk.DropDown): dropdown that emited `notify::selected` signal.
            _pspec (GObject.ParamSpec): Encapsulates the metadata required to specify parameters,
                such as GObject properties; not used.
            model_obj (GtkT): The operated view model object.
            prop_name (str): The name of a property which must be updated.
            ids: list of foreign keys ids.
        """
        selected_idx = dropdown.get_selected()
        new_id = ids[selected_idx]
        setattr(model_obj, prop_name, new_id)
        self.changed_items[hash(model_obj)] = model_obj

    def _on_db_changed(self, changed_sql_cls: type[SqlT]) -> None:
        """Handle saving/deletion in a table in the databse.

        Args:
            changed_sql_cls (type[SqlT]): SQLAlchemy ORM class which table was changed.
        """
        fk_configs = getattr(self.gtk_model_cls, "_fk_configs", {})

        # check if the changed table is one we rely on for a DropDown
        if changed_sql_cls in fk_configs.values():
            # this forces the ColumnView to re-bind all rows,
            # which re-runs the DropDown population logic
            self.list_store.load_all(self.sql_cls)

    def _string_to_type(self, value: str, prop_name: str) -> Any:
        """Helper to cast string back to the GObject property type.

        Args:
            value (str): The value that must be casted.
            prop_name (str): The name of the used GObject view model property.

        Returns:
            Any: The casted GObject view model property.
        """
        prop = self.gtk_model_cls.find_property(prop_name)
        if prop.value_type == GObject.TYPE_INT:
            return int(value) if value.isdigit() else 0
        if prop.value_type in (GObject.TYPE_DOUBLE, GObject.TYPE_FLOAT):
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0.0
        return value
