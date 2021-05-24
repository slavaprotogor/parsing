# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
from avito import settings
from avito import Session
from avito.models.apartment import Apartment


class AvitoPipeline:
    def process_item(self, item, spider):
        return item


class DataBasePipeline:
    """DataBasePipeline saves data to DB"""

    def __init__(self):
        self.db = Session()
        self._items_create = []
        self._items_udapte = []

    def _get_unique_items(self, items):
        items_unique = []
        for item in items:
            if item not in items_unique:
                items_unique.append(item)
        return items_unique

    def _run_update_items(self):
        self.db.bulk_update_mappings(Apartment, self._items_udapte)
        self.db.commit()
        self._items_udapte = []

    def _run_create_items(self):
        self.db.bulk_insert_mappings(Apartment, self._get_unique_items(self._items_create))
        self.db.commit()
        self._items_create = []

    def process_item(self, item, spider):

        product = self.db.query(Apartment).filter_by(id_a=item['id_a']).first()
        if product:
            # multi update
            if product.price != float(item['price']):
                self._items_udapte.append({
                    'id': product.id,
                    'price': item['price'],
                })
            if len(self._items_udapte) == settings.BULK_AMOUNT:
                self._run_update_items()
        else:
            # multi create
            self._items_create.append(item)
            if len(self._items_create) == settings.BULK_AMOUNT:
                self._run_create_items()

        return item

    def close_spider(self, spider):
        if self._items_create:
            self._run_create_items()
        if self._items_udapte:
            self._run_update_items()
        self.db.close()
