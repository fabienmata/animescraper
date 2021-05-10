# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class manga(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    _id = scrapy.Field()
    romaji_title = scrapy.Field()
    native_title = scrapy.Field()
    genre = scrapy.Field()
    mal_score = scrapy.Field()
    ani_score = scrapy.Field()
    kore_score = scrapy.Field()
    jon_score = scrapy.Field()
