from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


engine = create_engine('sqlite:///gb_parse.db', echo=True)


Session = sessionmaker(bind=engine)


def get_session():
    return Session()
