import scrapy


class SpideravitoSpider(scrapy.Spider):
    name = 'spideravito'
    allowed_domains = ['www.avito.ru']
    start_urls = ['https://www.avito.ru/krasnodar/kvartiry/prodam']

    def parse(self, response):
        pass
