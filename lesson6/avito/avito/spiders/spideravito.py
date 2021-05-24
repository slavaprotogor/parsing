import scrapy
from avito.items import AvitoItem


class SpideravitoSpider(scrapy.Spider):
    name = 'spideravito'
    allowed_domains = ['www.avito.ru']
    start_urls = ['https://www.avito.ru/krasnodar/kvartiry/prodam-ASgBAgICAUSSA8YQ']

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def _main_fotmat(self, value):
        if not value:
            return ''
        return value.strip()

    def _float_format(self, value):
        return float(value.replace(',', '.'))

    def parse(self, response):
        pages_amount = response.xpath('//span[starts-with(@class, "pagination-item-")][position()=last()-1]/text()').get()
        for next_page in range(int(pages_amount)):
            sign = '?'
            if '?' in response.url:
                sign = '&'
            yield response.follow(response.urljoin(f'{response.url}{sign}p={next_page}'), callback=self.parse_list)

    def parse_page(self, response):
        item = AvitoItem()
        item['url'] = response.url
        item['title'] = response.xpath('//h1[@class="title-info-title"]/span/text()').get()
        item['price'] = response.xpath('//span[@class="js-item-price"]/@content').get()
        item['address'] = response.xpath('//span[@class="js-item-price"]/@content').get()
        yield item
        
    def parse_list(self, response):
        for product in response.xpath('//a[starts-with(@class, "link-link-")]/@href'):
            yield response.follow(product.get(), callback=self.parse_page)
