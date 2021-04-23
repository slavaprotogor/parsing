import os
import sys
import logging
import json
import asyncio
from aiofile import async_open
import aiohttp


WORKER_NUM = 10
PARSING_DELAY = 0.2
RETRY = 4

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

CATEGORIES_URL = 'https://5ka.ru/api/v2/categories/'
PRODUCTS_URL = ('https://5ka.ru/api/v2/special_offers/?store=&records_per_page=12&page={page}'
                '&categories={category}&ordering=&price_promo__gte=&price_promo__lte=&search=')


class Parser:
    """ Асинхронный парсер """

    headers_default = {
        'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36')
    }

    def __init__(self, categories_url, products_url, root_dir, headers=None):
        self._categories_url = categories_url
        self._products_url = products_url
        self._root_dir = root_dir
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
        os.makedirs(self._result_dir, exist_ok=True)

    def _init_logger(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.setLevel(logging.INFO)
        handler = logging.FileHandler(os.path.join(self._root_dir, 'parsing.log'))
        handler.setLevel(logging.INFO)
        handler.setFormatter(
            logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
        )
        self._logger.addHandler(handler)

    async def _parser(self, url):
        retry = 1
        while True:
            await asyncio.sleep(PARSING_DELAY)

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

    async def _producer(self, url):
        categories = await self._parser(url)
        for category in categories:
            self._q.put_nowait(category)

    async def _worker(self):
        while True:
            category = await self._q.get()
            self._logger.info('%s start!', category)
            products = await self._fetch_products(category)
            await self._write_to_file(category, products)
            self._q.task_done()
            self._logger.info('%s done!', category)

    async def _write_to_file(self, category, products):
        category_name = category['parent_group_name'].replace(' ', '_')
        async with async_open(os.path.join(self._result_dir, f'{category_name}.json'), 'w') as afp:
            await afp.write(
                json.dumps(
                    {
                        'name': category['parent_group_name'],
                        'code': category['parent_group_code'],
                        'products': products,
                    },
                    ensure_ascii=False,
                    separators=(',', ':')
                )
            )

    async def _fetch_products(self, category):
        page = 1
        products_result = []
        while True:
            url = self._products_url.format(
                    page=page,
                    category=category['parent_group_code'],
                )
            products = await self._parser(url)
            if not products.get('results'):
                return products_result
            products_result += products['results']
            page += 1

    async def _run(self):
        await self._producer(self._categories_url)

        await self._q.join()

        for worker in self._workers:
            worker.cancel()

    def run(self):
        self._logger.info('START')
        try:
            self._loop.run_until_complete(parser._run())
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
