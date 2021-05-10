import scrapy
import pymongo
from postscrape.items import manga
import time
import re
import requests
import json
from lxml import html

client = pymongo.MongoClient('localhost', 27017)

mydb = client["scrap_anime"]
collection = mydb["anime"]

class PostsSpider(scrapy.Spider):
    name = "final"
   
    def start_requests(self):
        url = "https://myanimelist.net/anime/season/2020/summer"
        yield scrapy.Request(url=url, callback=self.parse)
    
    def parse(self,response):
        #prendre la liste des animé de l'été 
        anime_dirty = response.xpath('//div[@class="seasonal-anime-list js-seasonal-anime-list js-seasonal-anime-list-key-1 clearfix"]//h2/a/text()').extract()
        anime_titles = [*anime_dirty[0:20]]
        
        #préparer la liste des animes en japonais (sur le site japonais anikore)
        #l'idée c'est de matcher le titre standard (de notre site d'origine qui lui aussi contient un nom japonais),
        # puis de racorder le nom obtenu avec le nom japonais dans le site d'arrivée)
        liens = ['https://www.anikore.jp/chronicle/2020/summer/ac:tv/', 'https://www.anikore.jp/chronicle/2020/summer/ac:tv/page:2']
        jap_complete = []
        for lien in liens : 
            anikore = requests.get(lien)
            tree = html.fromstring(anikore.content)
            title_jap_dirty = tree.xpath('//div[@class = "l-searchPageRanking_unit"]//h2/a/span[@class="l-searchPageRanking_unit_title"]/text()')
            title_jap_still_dirty = [z.strip() for z in title_jap_dirty if z.strip()]
            jap_clean =  [z[:len(z)-9] for z in title_jap_still_dirty]
            jap_complete.extend(jap_clean)

        #préparer la liste des animes en français (même idée)
        nautil = requests.get('https://www.nautiljon.com/animes/%C3%A9t%C3%A9-2020.html?format=1&y=0&tri=p&public_averti=1&simulcast=')
        arbre = html.fromstring(nautil.content)
        fr_clean = arbre.xpath('//div[@class="title"]/h2/a/text()')

        iteration = 1
        for  anime_title in anime_titles :
            
            time.sleep(2) 
            item = manga()
            item["_id"] = iteration

            #anilist a la meilleure base de données donc j'ai décidé d'utiliser leur api pour 
            #obtenir les noms japonais et j'ai aussi pris les notes et le genre
            #requête à leur api pour obtenir un dict de cette forme
            get_info = ''' query ( $search: String) { Media (search: $search, type: ANIME){ title {native} averageScore genres } } '''
            eng_title = {'search': anime_title}
            ani_url ='https://graphql.anilist.co'
            anilist = requests.post(ani_url, json={'query': get_info, 'variables': eng_title})
            #transformer en json puis prendre toutes les infos
            data = anilist.json()
            dirt = data['data']['Media']
            ani_score  = dirt['averageScore'] 
            native_title  = dirt['title']['native']

            #matcher le titre en japonais venant du site anglais avec un titre dans la liste du titre japonais 
            #prendre les 3 premières caractères est optimale dans notre cas
            for jap_title in jap_complete:
                if native_title[:2] == jap_title[:2] :
                    native_title = jap_title
                else : native_title= native_title

            genre = dirt['genres']
            #genre = str(genres).strip('[]')

            item["romaji_title"] = anime_title

            #matcher les titres avec les titres en français 
            jon_title = anime_title
            for fr_title in fr_clean:
                if jon_title[:3] == fr_title[:3] :
                    jon_title = fr_title
                else : jon_title= jon_title

            item["native_title"] = native_title
            item["genre"]= genre
            item["ani_score"]= ani_score
            item["mal_score"]= ""
            item["kore_score"]= ""
            item["jon_score"]= ""

            #création des liens pour parser les différents sites en utilisant les noms qu'on vient d'obtenir 
            anime_mal = "https://myanimelist.net/search/all?q=" + "%20".join(anime_title.split(" ")) + "&cat=all"
            ani_kore = "https://www.anikore.jp/anime_title/" + native_title + "/"
            jon_search = "-".join(jon_title.split(":"))
            nautiljon = "https://www.nautiljon.com/animes/" + "+".join(jon_search.split(" ")) +".html"

            collection.insert_one(dict(item))
            #requête à chaque url pour chaque anime 
            yield scrapy.Request(url=anime_mal, callback=self.parse_mal1, meta={'item': item,'origin':"mal"})
            yield scrapy.Request(url = ani_kore, callback=self.parse_kore, meta={'item': item,'origin':"kore"})
            yield scrapy.Request(url = nautiljon, callback=self.parse_jon, meta={'item': item,'origin':"jon"})
            iteration += 1
    #parsin de la page de recherche de mal puis suivre le lien du premier résultat
    def parse_mal1(self, response):
        time.sleep(2)
        item = response.meta['item']
        href = response.xpath('//div[@class="information di-tc va-t pt4 pl8"]/a/@href').get()   

        if response.meta["origin"] == "mal":
            yield scrapy.Request(url=href, callback=self.parse_mal2, meta={'item': item}) 
        elif response.meta["origin"] == "kore": 
            yield scrapy.Request(url=href, callback=self.parse_kore, meta={'item': item})
        else : 
            yield scrapy.Request(url=href, callback=self.parse_jon, meta={'item': item})
    
    def parse_mal2(self,response):
        try:
            rakoto = response.xpath('//div[@class="fl-l score"]//text()').extract()
            #on obtient une list donc : 
            text = rakoto[0].strip()
        except:
            text = float("NaN")
        item = response.meta["item"]
        #mettre le score au meme unité que les autres 
        mal_score =  round(float(text)*10, ndigits=1)
        item["mal_score"] = mal_score
        collection.update_one({"_id":item["_id"]},{'$set':{ "mal_score": item["mal_score"] }})
        yield item

    def parse_kore(self, response):
        time.sleep(2)
        item = response.meta['item']
        try:
            kore_score =  response.xpath('//section[@class="l-searchPageRanking"]//a/span//text()').extract_first()
        except:
            kore_score = float("NaN")
        item = response.meta["item"]
        item["kore_score"] = float(kore_score)
        collection.update_one({"_id":item["_id"]},{'$set':{ "kore_score": item["kore_score"] }})
        yield item

    def parse_jon(self, response):
        time.sleep(2)
        item = response.meta['item']
        try:
            jon_sco =  response.xpath('//div[@class = "moyNote"]//span[@itemprop="ratingValue"]/text()').extract()
            jon_sco_li = jon_sco[0].strip()
        except:
            jon_score = float("NaN")
        item = response.meta["item"]
        jon_score = round(float(jon_sco_li)*10, ndigits=1)
        item["jon_score"] = jon_score
        collection.update_one({"_id":item["_id"]},{'$set':{ "jon_score": item["jon_score"] }})
        yield item


        