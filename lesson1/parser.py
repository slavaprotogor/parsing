import os
import json
import logging

import asyncio
import aiohttp
from aiofile import async_open


WORKER_NUM = 10
PARSING_DELAY = 0.1
RETRY = 4

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

CATEGORIES_URL = 'https://5ka.ru/api/v2/categories/'
PRODUCTS_URL = ('https://5ka.ru/api/v2/special_offers/?store=&records_per_page={per_page}&page={page}'
                '&categories={category}&ordering=&price_promo__gte=&price_promo__lte=&search=')


class Parser:
    """ Асинхронный парсер """

    headers_default = {
        'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36')
    }

    def __init__(self, categories_url: str, products_url: str,
                 root_dir: str, per_page: int=20, headers: dict=None):

        if not isinstance(root_dir, str):
            raise TypeError('Parameter "root_dir" must be a str')

        if not os.path.isdir(root_dir):
            raise ValueError(f'Parameter "root_dir={root_dir}" dir does not exist')

        self._root_dir = root_dir

        self._categories_url = categories_url
        self._products_url = products_url
        self._per_page = per_page
        self._headers = self.headers_default

        if headers:
            if not isinstance(headers, dict):
                raise TypeError('Parameter "headers" must be a dict')
            self._headers.update(headers)

        self._loop = asyncio.get_event_loop()
        self._q = asyncio.Queue()
        self._workers = [self._loop.create_task(self._worker()) for _ in range(WORKER_NUM)]

        self._init_result_dir()
        self._init_logger()

    def _init_result_dir(self):
        self._result_dir = os.path.join(self._root_dir, 'result')
        self._make_dirs(self._result_dir)

    def _init_logger(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.setLevel(logging.INFO)
        handler = logging.FileHandler(os.path.join(self._root_dir, 'parsing.log'))
        handler.setLevel(logging.INFO)
        handler.setFormatter(
            logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
        )
        self._logger.addHandler(handler)

    def _make_dirs(self, path):
        os.makedirs(path, exist_ok=True)

    async def _request(self, url):
        retry = 1
        while True:
            async with aiohttp.ClientSession(headers=self._headers) as session:
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            return await response.json()
                except aiohttp.ClientError as e:
                    self._logger.warning('Parsing %s, error: %s', url, e)

            if retry == RETRY:
                return []
            retry += 1
            await asyncio.sleep(PARSING_DELAY)

    async def _fetch_subcategories(self, category_name, category_code, path):
        subcategories = await self._request(f'{self._categories_url}{category_code}')
        if not subcategories:
            await self._q.put({
                'name': category_name,
                'code': category_code,
                'path': path,
            })
        else:
            path = os.path.join(path, category_name.replace(' ', '_'))
            for subcategory in subcategories:
                await self._fetch_subcategories(
                    subcategory['group_name'],
                    subcategory['group_code'],
                    path,
                )

    async def _fetch_categories(self, url):
        categories = await self._request(url)
        for category in categories:
            await self._fetch_subcategories(
                category['parent_group_name'],
                category['parent_group_code'],
                self._result_dir,
            )

    async def _worker(self):
        while True:
            category = await self._q.get()
            products = await self._fetch_products(category)
            await self._write_to_file(category, products)
            self._q.task_done()

    async def _write_to_file(self, category, products):
        category_name = category['name'].replace(' ', '_')
        await self._loop.run_in_executor(
            None,
            self._make_dirs,
            category['path']
        )
        async with async_open(os.path.join(category['path'], f'{category_name}.json'), 'w') as afp:
            category['products'] = products
            category.pop('path', None)
            await afp.write(
                json.dumps(
                    category,
                    ensure_ascii=False,
                    separators=(',', ':'),
                )
            )

    async def _fetch_products(self, category):
        page = 1
        products_result = []
        while True:
            url = self._products_url.format(
                    page=page,
                    per_page=self._per_page,
                    category=category['code'],
                )
            products = await self._request(url)
            if not products.get('results'):
                return products_result
            products_result += products['results']
            page += 1

    async def _run(self):
        await self._fetch_categories(self._categories_url)

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
        CATEGORIES_URL,
        PRODUCTS_URL,
        ROOT_DIR,
    )
    parser.run()
