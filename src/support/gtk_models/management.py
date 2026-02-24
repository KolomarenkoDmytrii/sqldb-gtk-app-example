# pylint: disable=wrong-import-position
"""Utilities related to dynamic GObject view model classes
creation and syncronization.
"""

from typing import (
    TypeVar,
    Any,
    Protocol,
    runtime_checkable,
    Optional,
    Callable,
    Sequence,
    Self,
)

from sqlalchemy import orm, String, Integer, Float, Boolean, select

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GObject


SqlT = TypeVar("SqlT", bound=orm.DeclarativeBase)
"""TypeVar: Generic type for SQLAlchemy ORM classes"""
GtkT = TypeVar("GtkT", bound="GtkDataModelProtocol")
"""TypeVar: Generic type for GtkDataModelProtocol view models"""


@runtime_checkable
class GtkDataModelProtocol(Protocol):
    """The interface for dynamically generated GObject classes.
    Those GObject classes serve as GTK view models for SQLAlchemy data models.
    """

    def to_sql_object(self) -> Any:
        """Convert GObject view model back to SQLAlchemy data model object.

        Returns:
            Any: data model object of related SQLAlchemy ORM class.
        """

    @classmethod
    def from_sql_object(cls: type[GtkT], sql_obj: SqlT) -> GtkT:
        """Create a GObject view model object from a SQLAlchemy ORM class object.

        Args:
            cls (type[GtkT]): The raleted view model class.
            sql_obj (SqlT): SQLAlchemy ORM class object from which
                view model of class `cls` will be created.

        Returns:
            GtkT: A converted view model object of class `cls`.
        """

    def get_property(self, property_name: str) -> Any:
        """Get a GObject property by its name.

        Args:
            property_name (str): the name of a property.

        Returns:
            Any: A GObject property object.
        """

    def set_property(self, property_name: str, value: Any) -> None:
        """Set value for named GObject property.

        Args:
            property_name (str): The name of a property.
            value (Any): The set value of a property.
        """

    @classmethod
    def find_property(cls, property_name: str) -> Any:
        """Find a GObject property by its name.

        Args:
            property_name (str): The name of a property.

        Returns:
            Any: A GObject property object.
        """


class TypeMapper: # pylint: disable=too-few-public-methods
    """Centralized mapping of SQL types to GObject types."""

    MAPPING = {
        Integer: int,
        String: str,
        Float: float,
        Boolean: bool,
    }

    @classmethod
    def get_py_type(cls, sql_column_type: Any) -> Optional[type]:
        """Get Python type related to SQLAlchemy column type.

        Args:
            sql_column_type (Any): SQLAlchemy column type

        Returns:
            Optional[type]: Related to a SQLAlchemy column type a Python type
        """
        for sql_type, py_type in cls.MAPPING.items():
            if isinstance(sql_column_type, sql_type):
                return py_type
        return None


def gtk_data_model(sql_cls: type[SqlT]) -> type[GtkDataModelProtocol]:
    """Create GObject view model class that implements `GtkDataModelProtocol`
    from SQLAlchemy ORM class `sql_cls` dynamically.

    Args:
        sql_cls (type[SqlT]): SQLAlchemy ORM class from which create
            a new GObject view model.

    Returns:
        type[GtkDataModelProtocol]: Related to `sql_cls` the GObject view model.
    """
    props: dict[str, GObject.Property] = {}
    # store which columns are foreign keys
    fk_metadata: dict[str, type[Any]] = {}

    mapper: orm.Mapper = orm.class_mapper(sql_cls)
    for column in mapper.columns:
        prop_name = column.key
        py_type = TypeMapper.get_py_type(column.type)
        if py_type:
            props[column.key] = GObject.Property(type=py_type)

            # check for foreign keys
            if column.foreign_keys:
                # get the target table name
                fk = list(column.foreign_keys)[0]
                target_table = fk.column.table

                # find the class associated with this table in the registry
                for mapper_val in sql_cls.registry.mappers:
                    if mapper_val.local_table == target_table:
                        fk_metadata[prop_name] = mapper_val.class_

    dynamic_gtk_model_cls: type = type(
        sql_cls.__name__ + "GtkBase", (GObject.GObject,), props
    )

    class GtkDataModel(dynamic_gtk_model_cls):
        """Base class for GObject view model classes."""

        _sql_cls = sql_cls
        _fk_configs = fk_metadata

        def __init__(self, **kwargs: Any) -> None:
            """Create GObject view model object.

            Args:
                **kwargs (Any): Set of GObject properties values.
            """
            super().__init__()
            for key, value in kwargs.items():
                if hasattr(self, key):
                    self.set_property(key, value)

        @classmethod
        def from_sql_object(cls: type[Self], obj: SqlT) -> Self:
            """Create a GObject view model object from SQLAlchemy ORM class object.

            Args:
                cls (type[Self]): The raleted view model class.
                sql_obj (SqlT): SQLAlchemy ORM class object from which
                    view model of class `cls` will be created.

            Returns:
                Self: A converted view model object of class `cls`.
            """
            data = {}
            for c in mapper.columns:
                val = getattr(obj, c.key)
                if c.primary_key and val is None:
                    val = 0
                data[c.key] = val

            return cls(**data)

        def to_sql_object(self) -> SqlT:
            """Convert GObject view model back to SQLAlchemy data model object.

            Returns:
                SqlT: data model object of related SQLAlchemy ORM class.
            """
            data = {}
            for c in mapper.columns:
                val = getattr(self, c.key)
                # if it's the primary key and the value is 0,
                # set it to None so SQLAlchemy knows to INSERT.
                if c.primary_key and val == 0:
                    val = None
                data[c.key] = val

            return self._sql_cls(**data)

    return GtkDataModel


class DataRepository:
    """Handles data persistence of GObject view models."""

    def __init__(self, session_factory: Callable[[], orm.Session]) -> None:
        """Create a data repository.

        Args:
            session_factory (Callable[[], orm.Session]): SQLAlchemy session factory.
        """
        self.session_factory = session_factory
        # List of callbacks to run after any save/delete
        self._on_change_callbacks: list[Callable[[type], None]] = []

    def subscribe_to_changes(self, callback: Callable[[type], None]) -> None:
        """Subscribe to changes made.

        Args:
            callback: Callable[[type], None]: A callback function
                that will be called when data change occurs.
        """
        self._on_change_callbacks.append(callback)

    def _notify_changes(self, sql_cls: type[SqlT]) -> None:
        """Notify subscribes about changes in `sql_class` related table.

        Args:
            sql_cls (type[SqlT]): SQLAlchemy ORM class which table
                has changes made in its data.
        """
        for callback in self._on_change_callbacks:
            callback(sql_cls)

    def save(self, gtk_models: Sequence[GtkT]) -> None:
        """Syncs models implementing GtkDataModelProtocol to the database.

        Args:
            gtk_models (Sequence[GtkT]): List of GObject view model
                objects to sync.
        """
        with self.session_factory() as session:
            merged_objs = []
            for gtk_model in gtk_models:
                sql_obj = gtk_model.to_sql_object()
                merged_objs.append(session.merge(sql_obj))
            session.commit()

            # refresh to get the ID back from the database
            for merged_obj in merged_objs:
                session.refresh(merged_obj)

            # sync generated IDs/server-side values back to GObject
            mapper: orm.Mapper = orm.class_mapper(sql_obj.__class__)
            for gtk_model, merged_obj in zip(gtk_models, merged_objs):
                for pk in mapper.primary_key:
                    setattr(gtk_model, pk.name, getattr(merged_obj, pk.name))

            # notify that this specific type has changed
            # this assumes all GtkT objects are related to one SQL class
            self._notify_changes(type(gtk_models[0].to_sql_object()))

    def delete(self, gtk_models: Sequence[GtkT]) -> None:
        """Delete data of models implementing GtkDataModelProtocol from the database.

        Args:
            gtk_models (Sequence[GtkT]): List of GObject view model
                objects to delete.
        """
        with self.session_factory() as session:
            for gtk_model in gtk_models:
                temp_sql_obj = gtk_model.to_sql_object()
                sql_cls = type(temp_sql_obj)
                mapper = orm.class_mapper(sql_cls)

                # extract the PK value (e.g., the ID)
                pk_val = getattr(temp_sql_obj, mapper.primary_key[0].name)

                if pk_val == 0 or pk_val is None:
                    # if it has no ID, it's not in the DB anyway
                    continue

                # retrieve the tracked instance from the DB
                db_obj = session.get(sql_cls, pk_val)

                if db_obj:
                    session.delete(db_obj)
                    # # Set a flag on the UI model if you've defined this property
                    # if hasattr(gtk_model, "is_deleted"):
                    #     gtk_model.is_deleted = True

            session.commit()

        # notify that this specific type has changed
        # this assumes all GtkT objects are related to one SQL class
        self._notify_changes(type(gtk_models[0].to_sql_object()))

    def fetch_all(
        self, sql_cls: type[SqlT], gtk_model_cls: type[GtkT]
    ) -> Sequence[GtkT]:
        """Fetches all records and converts them to GObject view models.

        Args:
            sql_cls (type[SqlT]): SQLAlchemy ORM class.
            gtk_model_cls (type[GtkT]): GObject view model class related to `sql_cls`.

        Returns:
            Sequence[GtkT]: Fetched GObject view models.
        """
        with self.session_factory() as session:
            stmt = select(sql_cls)
            results = session.scalars(stmt).all()

            return [gtk_model_cls.from_sql_object(obj) for obj in results]
