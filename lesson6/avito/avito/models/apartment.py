from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float


Base = declarative_base()


class Apartment(Base):
    """
    Model of a Apartment avito
    """
    __tablename__ = 'avito_apartment'

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_a = Column(String(30), index=True, unique=True)
    url = Column(String(256))
    title = Column(String(512))
    price = Column(Integer)
    address = Column(String(512))
    parameters = Column(String(512))
    author_link = Column(String(256))
    author_phone = Column(String(12))

    def __repr__(self):
        return f'<Apartment(id='{self.id}', name='{self.title}', price='{self.price}')>'
