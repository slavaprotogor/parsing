import os
import dotenv
from scrapy.crawler import CrawlerProcess
from scrapy.settings import Settings
from insta.spiders.instaspider import InstaspiderSpider


if __name__ == '__main__':
    dotenv.load_dotenv('.env')
    crawler_settings = Settings()
    crawler_settings.setmodule('insta.settings')
    crawler_process = CrawlerProcess(settings=crawler_settings)
    crawler_process.crawl(
        InstaspiderSpider,
        login=os.getenv('INST_LOGIN'),
        password=os.getenv('INST_PASSWORD')
    )
    crawler_process.start()
