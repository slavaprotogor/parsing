import os
import json
import logging
from bs4 import BeautifulSoup

import asyncio
import aiohttp
import motor.motor_asyncio
from pymongo.errors import PyMongoError


WORKER_NUM = 10
PARSING_DELAY = 0.4
RETRY = 4

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

START_URL = 'https://gb.ru/posts/'


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
            self._logger.info('start connection to mongodb')
            self._client = motor.motor_asyncio.AsyncIOMotorClient(
                self.mongodb_connection, io_loop=self._loop)
        except PyMongoError as e:
            self._logger.exception('MongoDB error: %s', e)
        self._db = self._client[self.db_name]
        self._collection = self._db[self.db_collection_name]
        self._logger.info('done connection to mongodb')

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
        pg_ul = page_start_soup.find('ul', {'class': 'gb__pagination'})
        pg_li = pg_ul.findChildren('li' , recursive=False)[-2]
        count = pg_li.findChildren('a' , recursive=False)[0].getText()
        for page in range(1, 3):  # int(count) + 1):
            page_url = f'{self._start_url}?page={page}'
            page_text = await self._request(page_url)
            page_soup = BeautifulSoup(page_start, 'html.parser')
            post_links = list(set([self._start_url.replace('/posts/', link['href'])
                          for link in page_soup.select('div.post-item a:first-child')]))
            await self._q.put(post_links)

    async def _fetch_post_data(self, url):
        await asyncio.sleep(PARSING_DELAY)
        post_text = await self._request(url)
        post_soup = BeautifulSoup(post_text, 'html.parser')
        return {
            'url': url,
            #'title': post_soup.select('h1.blogpost-title')[0].text,
            #'image': post_soup.select('img:first-child')[0]['src'],
            #'datetime': post_soup.select('.blogpost-date-views time')[0]['datatime'],
            #'author': post_soup.find('div', {'item': author}).text,
        }

    async def _save_to_database(self, data: list):
        try:
            await self._collection.insert_many(data)
        except PyMongoError as e:
            self._logger.exception('MongoDB error: %s', e)
            raise e
        self._logger.info('Insert data: %s', len(data))
        return True

    async def _worker(self):
        while True:
            self._logger.info('Worker start!')
            post_links = await self._q.get()
            self._logger.info(post_links)
            data = await asyncio.gather(*[self._fetch_post_data(post_link) for post_link in post_links[:5]])
            self._logger.info(data)
            await self._save_to_database(data)
            self._q.task_done()
            self._logger.info('done!')

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
