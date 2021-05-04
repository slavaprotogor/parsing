import os
import json
import logging
import datetime
from bs4 import BeautifulSoup

import asyncio
import aiohttp

from models import User, Comment, Post, Tag

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker


WORKER_NUM = 10
PARSING_DELAY = 0.4
RETRY = 4
PARSE_CHUNK = 3

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

START_URL = 'https://gb.ru/posts/'
COMMENTS_URL = 'https://gb.ru/api/v2/comments?commentable_type=Post&commentable_id={post_id}&order=desc'


class Parser:
    """ Асинхронный парсер """

    headers_default = {
        'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36')
    }


    def __init__(self, start_url: str, comments_url: str, root_dir: str,
                 per_page: int=20, headers: dict=None):

        if not isinstance(root_dir, str):
            raise TypeError('Parameter "root_dir" must be a str')

        if not os.path.isdir(root_dir):
            raise ValueError(f'Parameter "root_dir={root_dir}" dir does not exist')

        self._root_dir = root_dir

        self._start_url = start_url
        self._comments_url = comments_url
        self._per_page = per_page
        self._headers = self.headers_default

        if headers:
            if not isinstance(headers, dict):
                raise TypeError('Parameter "headers" must be a dict')
            self._headers.update(headers)

        self._loop = asyncio.get_event_loop()
        self._q = asyncio.Queue()
        self._workers = [self._loop.create_task(self._worker()) for _ in range(WORKER_NUM)]

        # database
        self._engine = None
        self._create_session = None

        self._init_logger()
        self._init_db()

    def _init_logger(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.setLevel(logging.INFO)
        handler = logging.FileHandler(os.path.join(self._root_dir, 'parsing.log'))
        handler.setLevel(logging.INFO)
        handler.setFormatter(
            logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
        )
        self._logger.addHandler(handler)

    def _init_db(self):
        self._engine = create_async_engine('sqlite+aiosqlite:///gb_parse.db', echo=True)
        self._create_session = sessionmaker(
            self._engine, expire_on_commit=False, class_=AsyncSession
        )

    def get_session(self):
        return self._create_session()

    def _parse_datetime(self, dt_str):
        dt, z = dt_str.split('+')
        z = z.replace(':', '')
        dt_obj = datetime.datetime.strptime(f'{dt}+{z}', "%Y-%m-%dT%H:%M:%S%z")
        return dt_obj

    async def _request(self, url):
        retry = 1
        while True:
            async with aiohttp.ClientSession(headers=self._headers) as session:
                try:
                    async with session.get(url, raise_for_status=True) as response:
                        return await response.text()
                except aiohttp.ClientError as e:
                    self._logger.warning('Requrest %s, error: %s', url, e)

            if retry == RETRY:
                return []
            retry += 1
            await asyncio.sleep(PARSING_DELAY)

    async def _parse_start(self, url):
        page_start = await self._request(url)
        page_start_soup = BeautifulSoup(page_start, 'html.parser')
        post_number = page_start_soup.find('ul', 'gb__pagination').\
                                      find_all('li')[-2].find('a').text
        for page in range(1, int(post_number) + 1):
            page_url = f'{self._start_url}?page={page}'
            page_text = await self._request(page_url)
            page_soup = BeautifulSoup(page_text, 'html.parser')
            post_links = [self._start_url.replace('/posts', item.find('a')['href'])
                          for item in page_soup.find_all('div', 'post-item event')]
            await self._q.put(post_links)

    async def _fetch_post_data(self, url):
        await asyncio.sleep(PARSING_DELAY)
        post_text = await self._request(url)

        post_soup = BeautifulSoup(post_text, 'html.parser')
        post_id = post_soup.find('div', 'referrals-social-buttons-small-wrapper')['data-minifiable-id']

        await asyncio.sleep(PARSING_DELAY)
        comments_raw = await self._request(self._comments_url.format(post_id=post_id))
        comments_dict = json.loads(comments_raw)

        image = post_soup.find('img')

        user = post_soup.find('div', {'itemprop': 'author'})
        user_url = user.parent['href']

        tags = []
        for t in post_soup.find_all('i', 'i i-tag m-r-xs text-muted text-xs'):
            tags += t['keywords'].split(', ')

        return {
            'post': {
                'url': url,
                'title': post_soup.find('h1', 'blogpost-title').text,
                'image': image['src'] if image else None,
                'datetime': self._parse_datetime(post_soup.select('.blogpost-date-views time')[0]['datetime']),
            },
            'user': {
                'user_gb_id': user_url.split('/')[-1],
                'name': user.text,
                'url': self._start_url.replace('/posts', user_url),
            },
            'comments': comments_dict,
            'tags': tags,
        }

    async def _save_to_database(self, data: list):
        session = self.get_session()

        for d in data:

            tags_append = []
            if d['tags']:
                
                for t in d['tags']:
                    tags = await session.execute(
                        select(Tag).
                        filter_by(name=t)
                    )

                    tags = tags.scalars().all()

                    tag = None
                    if not tags:
                        tag_new = Tag(name=t)
                        tags_append.append(tag_new)

                        session.add(tag_new)

                        await session.commit()
                    else:
                        tags_append.append(tags[0])

            users = await session.execute(
                select(User).
                filter_by(user_gb_id=d['user']['user_gb_id'])
            )

            users = users.scalars().all()

            user = None
            if not users:
                user = User(**d['user'])

                session.add(User(**d['user']))

                await session.commit()
            else:
                user = users[0]

            post_new = Post(**d['post'])
            post_new.user_id = user.id

            for tags_a in tags_append:
                post_new.tags.append(tags_a)

            session.add(post_new)

            await session.commit()

        await session.close()

        return True

    async def _worker(self):
        while True:
            post_links = await self._q.get()

            data = []
            for idx, item in enumerate(post_links[::PARSE_CHUNK]):
                parse_links = post_links[idx * PARSE_CHUNK: (idx + 1) * PARSE_CHUNK]

                if parse_links:
                    data_links = await asyncio.gather(*[self._fetch_post_data(parse_link)
                                                        for parse_link in parse_links])
                    data += data_links

                await self._save_to_database(data)
            self._q.task_done()

    async def _run(self):
        await self._parse_start(self._start_url)

        await self._q.join()

        for worker in self._workers:
            worker.cancel()

    def run(self):
        self._logger.info('START')
        try:
            self._loop.run_until_complete(parser._run())
        except Exception as e:
            self._logger.exception('Error: %s', e)
        finally:
            self._loop.close()
        self._logger.info('DONE')


if __name__ == '__main__':

    parser = Parser(
        START_URL,
        COMMENTS_URL,
        ROOT_DIR,
    )
    parser.run()
