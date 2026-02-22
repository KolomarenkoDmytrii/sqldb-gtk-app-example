from typing import (
    Type,
    TypeVar,
    Any,
    Dict,
    Protocol,
    runtime_checkable,
    Optional,
    Callable,
    Iterable,
    Sequence,
    Generic,
    Self,
    cast,
)

from sqlalchemy import orm, String, Integer, Float, Boolean, select

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GObject


# type Variable for Generic support
T_SQL = TypeVar("T_SQL", bound=orm.DeclarativeBase)
T_GTK = TypeVar("T_GTK", bound="GtkDataModelProtocol")


@runtime_checkable
class GtkDataModelProtocol(Protocol):
    """Defines the interface for dynamically generated models for static analysis."""

    def to_sql_object(self) -> Any: ...
    @classmethod
    def from_sql_object(cls: type[T_GTK], sql_obj: Any) -> T_GTK: ...
    def get_property(self, property_name: str) -> Any: ...
    def set_property(self, property_name: str, value: Any) -> None: ...


class TypeMapper:
    """Centralized mapping of SQL types to GObject types (Open/Closed Principle)."""

    MAPPING = {
        Integer: int,
        String: str,
        Float: float,
        Boolean: bool,
    }

    @classmethod
    def get_py_type(cls, sql_column_type: Any) -> Optional[type]:
        for sql_type, py_type in cls.MAPPING.items():
            if isinstance(sql_column_type, sql_type):
                return py_type
        return None


def gtk_data_model(sql_cls: type[T_SQL]) -> type[Any]:
    props: Dict[str, GObject.Property] = {}
    # Iterate over SQLAlchemy's mapper to find columns reliably
    mapper: orm.Mapper = orm.class_mapper(sql_cls)
    for column in mapper.columns:
        prop_name = column.key
        # Check if the column type (or its class) is in our map
        # Note: we use type(column.type) to get the class (e.g., <class 'sqlalchemy.sql.sqltypes.Integer'>)
        py_type = TypeMapper.get_py_type(column.type)
        if py_type:
            # We define the property name to match the SQL column key
            props[column.key] = GObject.Property(type=py_type)

    # Logic fix: We use GObject.GObject as the static base for Mypy's sake
    # but create the dynamic type for GTK's sake.
    DynamicGtkModel: type = type(sql_cls.__name__ + "GtkBase", (GObject.GObject,), props)

    class GtkDataModel(DynamicGtkModel):  
        is_deleted = GObject.Property(type=bool, default=False)

        # class GtkDataModel(cast(type[GObject.GObject], DynamicGtkModel)):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__()
            for key, value in kwargs.items():
                if hasattr(self, key):
                    self.set_property(key, value)

        @classmethod
        def from_sql_object(cls: type[Self], obj: T_SQL) -> Self:
            # data = {c.key: getattr(obj, c.key) for c in mapper.columns}
            data = {}
            for c in mapper.columns:
                val = getattr(obj, c.key)
                if c.primary_key and val == None:
                    val = 0
                data[c.key] = val

            return cls(**data)

        def to_sql_object(self) -> T_SQL:
            """Converts GObject properties back into a SQLAlchemy model instance."""
            # data = {c.key: self.get_property(c.key) for c in mapper.columns}
            data = {}
            for c in mapper.columns:
                val = getattr(self, c.key)
                # CRITICAL FIX:
                # If it's the primary key and the value is 0,
                # set it to None so SQLAlchemy knows to INSERT.
                if c.primary_key and val == 0:
                    val = None
                data[c.key] = val

            return sql_cls(**data)

    return GtkDataModel


# TODO: add delete() method
class DataRepository:
    """Handles Persistence with full type safety."""

    def __init__(self, session_factory: Callable[[], orm.Session]) -> None:
        self.session_factory = session_factory

    def save(self, gtk_models: Sequence[T_GTK]) -> None:
        """Syncs a model implementing GtkDataModelProtocol to the database."""
        with self.session_factory() as session:
            merged_objs = []
            for gtk_model in gtk_models:
                sql_obj = gtk_model.to_sql_object()
                merged_objs.append(session.merge(sql_obj))
            session.commit()

            # # Refresh to get the ID back from the database
            for merged_obj in merged_objs:
                session.refresh(merged_obj)

            # Sync generated IDs/Server-side values back to GObject
            mapper: orm.Mapper = orm.class_mapper(sql_obj.__class__)
            for gtk_model, merged_obj in zip(gtk_models, merged_objs):
                for pk in mapper.primary_key:
                    setattr(gtk_model, pk.name, getattr(merged_obj, pk.name))

    def delete(self, gtk_models: Sequence[T_GTK]) -> None:
        with self.session_factory() as session:
            for gtk_model in gtk_models:
                # 1. Get the SQL class and Primary Key from the model
                # We assume to_sql_object returns an instance of the class we need
                temp_sql_obj = gtk_model.to_sql_object()
                sql_cls = type(temp_sql_obj)
                mapper = orm.class_mapper(sql_cls)

                # 2. Extract the PK value (e.g., the ID)
                pk_val = getattr(temp_sql_obj, mapper.primary_key[0].name)

                if pk_val == 0 or pk_val is None:
                    # If it has no ID, it's not in the DB anyway
                    continue

                # 3. Retrieve the tracked instance from the DB
                db_obj = session.get(sql_cls, pk_val)

                if db_obj:
                    session.delete(db_obj)
                    # Set a flag on the UI model if you've defined this property
                    if hasattr(gtk_model, "is_deleted"):
                        gtk_model.is_deleted = True

            session.commit()

    # gtk_model_cls: type[T_GTK] ?
    def fetch_all(
        self, sql_cls: type[T_SQL], gtk_model_cls: type[T_GTK]
    ) -> Sequence[T_GTK]:
        """Fetches all records and converts them to Gtk Models."""
        with self.session_factory() as session:
            stmt = select(sql_cls)
            results = session.scalars(stmt).all()

            # We need the GTK class mapped to this SQL class
            # return [
            #     cast(GObject.Object, gtk_model_cls.from_sql_object(obj))
            #     for obj in results
            # ]
            return [gtk_model_cls.from_sql_object(obj) for obj in results]
