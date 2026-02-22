from sqlalchemy import orm, String, Integer, Float, Boolean

class Base(orm.DeclarativeBase):
    pass

class Product(Base):
    __tablename__ = "products"
    id: orm.Mapped[int] = orm.mapped_column(primary_key=True)
    name: orm.Mapped[str] = orm.mapped_column(String(40))
    description: orm.Mapped[str] = orm.mapped_column(String(300))


