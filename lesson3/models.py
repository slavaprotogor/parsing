from sqlalchemy import Table, Column, CHAR, String, Text, ForeignKey, Integer, DateTime
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import relationship

from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


posts_tags = Table('posts_tags', Base.metadata,
    Column('post_id', Integer, ForeignKey('post.id')),
    Column('tag_id', Integer, ForeignKey('tag.id'))
)


class User(Base):
    __tablename__ = 'user'
    __table_args__ = {
        'mysql_charset': 'utf8',
        'mysql_collate': 'utf8_general_ci',
    }

    id = Column(Integer, autoincrement=True, primary_key=True)
    name = Column(String(120), nullable=False, index=True)
    url = Column(String(120), nullable=False)


class Post(Base):
    __tablename__ = 'post'
    __table_args__ = {
        'mysql_charset': 'utf8',
        'mysql_collate': 'utf8_general_ci',
    }

    id = Column(Integer, autoincrement=True, primary_key=True)
    url = Column(String(256), nullable=False)
    title = Column(String(256), nullable=False, index=True)
    image = Column(String(256))
    datetime = Column(DateTime, nullable=False)

    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship('User', backref='posts')

    tags = relationship('Tag', secondary=posts_tags, backref='posts')


class Comment(Base):
    __tablename__ = 'comment'
    __table_args__ = {
        'mysql_charset': 'utf8',
        'mysql_collate': 'utf8_general_ci',
    }

    id = Column(Integer, autoincrement=True, primary_key=True)
    name = Column(String(120), nullable=False)
    title = Column(String(256), nullable=False)
    text = Column(Text, nullable=False)

    parent_id = Column(Integer, ForeignKey('comment.id'))
    childs = relationship('Comment')

    post_id = Column(Integer, ForeignKey('post.id'))
    post = relationship('Post', backref='comments')


class Tag(Base):
    __tablename__ = 'tag'
    __table_args__ = {
        'mysql_charset': 'utf8',
        'mysql_collate': 'utf8_general_ci',
    }

    id = Column(Integer, autoincrement=True, primary_key=True)
    name = Column(String(120), nullable=False, index=True)
