"""Module that contains explicit dynamic definitions of
GObject view models of SQLAlchemy ORM classes.
"""

from .. import models
from .management import gtk_data_model

# "type: ignore[misc]" is used because mypy doesn't support
# runtime creation of classes
# see: https://github.com/python/mypy/wiki/Unsupported-Python-Features


class ProductModel(gtk_data_model(models.Product)):  # type: ignore[misc]
    """Explicit class for Product GObject model."""


class OrderModel(gtk_data_model(models.Order)):  # type: ignore[misc]
    """Explicit class for Order GObject model."""
