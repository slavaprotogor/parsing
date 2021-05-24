# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class AvitoItem(scrapy.Item):
    url = scrapy.Field()
    title = scrapy.Field()
    price = scrapy.Field()
    address = scrapy.Field()
    parameters = scrapy.Field()
    author_link = scrapy.Field()
    author_phone = scrapy.Field()