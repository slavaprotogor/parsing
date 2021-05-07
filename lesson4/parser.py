import os
import json
import logging
from bs4 import BeautifulSoup
from lxml import html

import asyncio
import aiohttp
import motor.motor_asyncio
from pymongo.errors import PyMongoError


WORKER_NUM = 10
PARSING_DELAY = 0.4
RETRY = 4
PARSE_CHUNK = 3

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

START_URL = 'https://auto.youla.ru/sankt-peterburg/cars/used/'


class Parser:
    """ Асинхронный парсер """

    headers_default = {
        'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36')
    }

    mongodb_connection = 'mongodb://localhost:27017'
    db_name = 'parsing'
    db_collection_name = 'posts'

    def __init__(self, start_url: str, root_dir: str,
                 per_page: int=20, headers: dict=None):

        if not isinstance(root_dir, str):
            raise TypeError('Parameter "root_dir" must be a str')

        if not os.path.isdir(root_dir):
            raise ValueError(f'Parameter "root_dir={root_dir}" dir does not exist')

        self._root_dir = root_dir

        self._start_url = start_url
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
        self._client = None
        self._db = None

        self._init_logger()
        self._init_mongo_connection()

    def _init_logger(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.setLevel(logging.INFO)
        handler = logging.FileHandler(os.path.join(self._root_dir, 'parsing.log'))
        handler.setLevel(logging.INFO)
        handler.setFormatter(
            logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
        )
        self._logger.addHandler(handler)

    def _init_mongo_connection(self):
        try:
            self._client = motor.motor_asyncio.AsyncIOMotorClient(
                self.mongodb_connection, io_loop=self._loop)
        except PyMongoError as e:
            self._logger.exception('MongoDB error: %s', e)
        self._db = self._client[self.db_name]
        self._collection = self._db[self.db_collection_name]

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
        root = html.fromstring(page_start)
        page_count = root.xpath('//div[contains(@class, "Paginator_total__")]/text()')[1]

        for page in range(1, int(page_count)):
            page_url = f'{self._start_url}?page={page}'
            page_text = await self._request(page_url)
            page_root= html.fromstring(page_start)
            post_links = [self._start_url.replace('/posts', item.find('a')['href'])
                          for item in page_soup.find_all('div', 'post-item event')]
            await self._q.put(post_links)

    def _comments_str(self, comments):
        comments_str = ''
        for comment_dict in comments:
            for _, comment in comment_dict.items():
                if comment['children']:
                    comments_str += self._comments_str(comment['children'])
                comments_str += f'{comment["user"]["full_name"]}\n{comment["body"]}\n\n'
        return comments_str

    async def _fetch_post_data(self, url):
        await asyncio.sleep(PARSING_DELAY)
        post_text = await self._request(url)

        post_soup = BeautifulSoup(post_text, 'html.parser')
        post_id = post_soup.find('div', 'referrals-social-buttons-small-wrapper')['data-minifiable-id']

        await asyncio.sleep(PARSING_DELAY)
        comments_raw = await self._request(self._comments_url.format(post_id=post_id))
        comments_dict = json.loads(comments_raw)
        image = post_soup.find('img')
        return {
            'url': url,
            'title': post_soup.find('h1', 'blogpost-title').text,
            'image': image['src'] if image else None,
            'datetime': post_soup.select('.blogpost-date-views time')[0]['datetime'],
            'author': post_soup.find('div', {'itemprop': 'author'}).text,
            'author_url': self._start_url.replace('/posts', post_soup.find('div', {'itemprop': 'author'}).parent['href']),
            'comments': self._comments_str(comments_dict),
        }

    async def _save_to_database(self, data: list):
        try:
            await self._collection.insert_many(data)
        except PyMongoError as e:
            self._logger.exception('MongoDB error: %s', e)
            raise e
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
        ROOT_DIR,
    )
    parser.run()
