from sqlalchemy import orm, String, Integer, Float, Boolean, ForeignKey


class Base(orm.DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"
    id: orm.Mapped[int] = orm.mapped_column(primary_key=True)
    name: orm.Mapped[str] = orm.mapped_column(String(40))
    description: orm.Mapped[str] = orm.mapped_column(String(300))
    quantity: orm.Mapped[int] = orm.mapped_column(Integer())
    oreders: orm.Mapped[list["Order"]] = orm.relationship(cascade="all,delete")


class Order(Base):
    __tablename__ = "orders"
    id: orm.Mapped[int] = orm.mapped_column(primary_key=True)
    # product_id: orm.Mapped[int] = orm.mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    product_id: orm.Mapped[int] = orm.mapped_column(ForeignKey("products.id"))
    product: orm.Mapped["Product"] = orm.relationship()
    # product: orm.Mapped["Product"] = orm.relationship()
    quantity: orm.Mapped[int] = orm.mapped_column(Integer())
    


