# pylint: disable=too-few-public-methods
"""Module that contains definitions of SQLAlchemy ORM classes."""

from sqlalchemy import orm, String, Integer, ForeignKey


class Base(orm.DeclarativeBase):
    """Base class for all defined ORM classes."""


class Product(Base):
    """Class for products."""

    __tablename__ = "products"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True)
    # the property 'name' is needed for the dropdown in UI table
    name: orm.Mapped[str] = orm.mapped_column(String(40))
    description: orm.Mapped[str] = orm.mapped_column(String(300))
    quantity: orm.Mapped[int] = orm.mapped_column(Integer())
    orders: orm.Mapped[list["Order"]] = orm.relationship(
        cascade="all,delete", back_populates="product"
    )


class Order(Base):
    """Class for orders."""

    __tablename__ = "orders"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True)
    product_id: orm.Mapped[int] = orm.mapped_column(ForeignKey("products.id"))
    product: orm.Mapped["Product"] = orm.relationship(back_populates="orders")
    quantity: orm.Mapped[int] = orm.mapped_column(Integer())
