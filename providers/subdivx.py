import os
import time
from exceptions import (ParseResponseException, ServiceUnavailableException,
						SubtitlesNotFoundException)
from parser import ParserBeautifulSoup

from requests import Session
from guessit import guessit

from subtitles import SubdivxSubtitle, SubdivxSubtitleResults


class Subdivx:
	BASE_URL = "https://www.subdivx.com/"

	def __init__(self, logger, proxy_pool, timeout=60):
		self.session = None
		self.logger = logger
		self.logger.name = "subdivx"
		self.proxy = None
		self.proxy_pool = proxy_pool
		self.timeout = timeout
		self.multi_result_throttle = 2

	def __enter__(self):
		self.session = Session()
		self.session.headers['User-Agent'] = 'SubtitlesDownloader/2.x'
		if self.proxy_pool != None:
			self.proxy = next(self.proxy_pool)
			self.logger.info(f'Requests with proxy {self.proxy}')
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.session.close()
		return

	def query(self, keyword, season=None, episode=None, year=None):
		query = keyword
		if season and episode:
			query += ' S{season:02d}E{episode:02d}'.format(season=season, episode=episode)
		elif year:
			query += ' {:4d}'.format(year)

		params = {
			'buscar': query,  # search string
			'accion': 5,  # action search
			'oxdown': 1,  # order by downloads descending
			'pg': 1  # page 1
		}

		subtitles = []
		search_link = self.BASE_URL + 'index.php'
		
		proxies = None
		if self.proxy != None:
			proxies = {"https": self.proxy}
		
		while True:
			response = self.session.get(search_link, params=params, timeout=self.timeout, proxies=proxies)
			if response.status_code != 200:
				raise ServiceUnavailableException('Bad status code: ' + str(response.status_code))

			try:
				page_subtitles = self.parse_subtitles_page(response)
			except Exception as e:
				raise ParseResponseException('Error parsing subtitles list: ' + str(e))

			subtitles += page_subtitles

			if len(page_subtitles) >= 20:
				params['pg'] += 1  # search next page
				time.sleep(self.multi_result_throttle)
			else:
				break
			
			if params['pg'] == 10:
				break

		return subtitles

	def parse_subtitles_page(self, response):
		subtitles = []
	
		page_soup = ParserBeautifulSoup(response.content.decode('iso-8859-1', 'ignore'), ['lxml', 'html.parser'])
		title_soups = page_soup.find_all("div", {'id': 'menu_detalle_buscador'})
		body_soups = page_soup.find_all("div", {'id': 'buscador_detalle'})

		for subtitle in range(0, len(title_soups)):
			title_soup, body_soup = title_soups[subtitle], body_soups[subtitle]
			title = title_soup.find("a").text.replace("Subtitulo de ", "")
			page_link = title_soup.find("a")["href"].replace('http://', 'https://')
			description = body_soup.find("div", {'id': 'buscador_detalle_sub'}).text
			subtitle = SubdivxSubtitle(page_link, description, title)
			subtitles.append(subtitle)

		return subtitles

	def search_subtitles(self, video_path, video_info):
		self.logger.info((f'Searching subtitles for {video_path}'))

		video_type = video_info.get("type")
		title = video_info.get("title")
		year = video_info.get("year")

		subtitles = []
		if video_type == 'episode':
			season = video_info.get("season")
			episode = video_info.get("episode")
			subtitles = self.query(title, season=season, episode=episode, year=year)
		elif video_type == 'movie':
			subtitles = self.query(title, year=year)

		if not subtitles:
			raise SubtitlesNotFoundException(video_path)

		return SubdivxSubtitleResults(subtitles)

	def download_by_path(self, video_path):
		video_info = guessit(video_path)
		subtitles = self.search_subtitles(video_path, video_info)
		subtitle = subtitles.get_qualified(video_info)
		self.logger.info('Subtitle found')
		self.logger.info(f'Downloading subtitle for {video_path}')
		return subtitle.download(self.session, self.timeout, self.proxy, video_path, video_info)
