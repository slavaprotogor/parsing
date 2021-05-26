import json
import scrapy


class InstaspiderSpider(scrapy.Spider):
    name = 'instaspider'
    allowed_domains = ['www.instagram.com']
    start_urls = ['https://www.instagram.com/accounts/login/']
    _url_login = 'https://www.instagram.com/accounts/login/ajax'

    def __init__(self, login, password, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._login = login
        self._password = password

    def parse(self, response):
        js_data = self.get_data_js(response)

        yield scrapy.FormRequest(
            self._url_login,
            method='POST',
            callback=self.parse,
            formdata={
                'username': self._login,
                'enc_password': self._password,
            },
            headers={
                'X-CSRFToken': js_data['config']['csrf_token'],
            }
        )

    def get_data_js(self, response):
        script = response.xpath(
            '//script[contains(text(), "window._shareData =")]/text()'
        ).extract_first()
        return json.loads(script.replace('window._shareData = ', '')[:-1])

