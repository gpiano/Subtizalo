import os
import random
from exceptions import (LoginException, LogoutException, NotLoggedInException,
						SizeTooSmallException, SubtitlesNotFoundException,
						TooManyTriesException, UnknownResultException)
from xml.etree import ElementTree

import requests
from guessit import guessit

from files import FileInfo
from subtitles import BSPlayerSubtitle, BSPlayerSubtitleResults


class BSPlayerDecorators:
	@classmethod
	def requires_login(cls, func):
		def wrapped(self, *args, **kwargs):
			if not self.token:
				raise NotLoggedInException('You need to be authenticated to perform this action')
			return func(self, *args, **kwargs)

		return wrapped


class BSPlayer:
	SUB_DOMAINS = ['s1', 's2', 's3', 's4', 's5', 's6', 's7', 's8', 's9',
				   's101', 's102', 's103', 's104', 's105', 's106', 's107', 's108', 's109']

	API_URL_TEMPLATE = "http://{sub_domain}.api.bsplayer-subtitles.com/v1.php"

	HEADERS = {
		'User-Agent': 'BSPlayer/2.x (1022.12362)',
		'Content-Type': 'text/xml; charset=utf-8',
		'Connection': 'close'
	}

	DATA_FORMAT = ('<?xml version="1.0" encoding="UTF-8"?>\n'
				   '<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" '
				   'xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" '
				   'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
				   'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
				   'xmlns:ns1="{search_url}">'
				   '<SOAP-ENV:Body SOAP-ENV:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
				   '<ns1:{func_name}>{params}</ns1:{func_name}></SOAP-ENV:Body></SOAP-ENV:Envelope>')

	APP_ID = 'BSPlayer v2.67'

	@classmethod
	def get_sub_domain(cls):
		sub_domain = random.choice(cls.SUB_DOMAINS)
		return cls.API_URL_TEMPLATE.format(sub_domain=sub_domain)

	def __init__(self, logger, proxy_pool, timeout=None, tries=5):
		self.logger = logger
		self.logger.name = "BSPlayer"
		self.search_url = self.get_sub_domain()
		self.token = None
		self.proxy = None
		self.proxy_pool = proxy_pool
		self.timeout = timeout
		self.tries = tries

	def __enter__(self):
		self.login()
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		return self.logout()

	def api_request(self, func_name, params=''):
		soap_action_header = f'"http://api.bsplayer-subtitles.com/v1.php#{func_name}"'
		headers = self.HEADERS.copy()
		headers['SOAPAction'] = soap_action_header

		data = self.DATA_FORMAT.format(search_url=self.search_url, func_name=func_name, params=params)
		
		self.logger.info(f'Sending request: {func_name}')
		
		proxies = None
		if self.proxy != None:
			proxies = {"https": self.proxy}
		
		for i in range(self.tries):
			try:
				self.logger.info(f'Try number {i+1} for operation {func_name}')
				res = requests.post(self.search_url, data=data, headers=headers, timeout=self.timeout, proxies=proxies)
				return ElementTree.fromstring(res.content)
			except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, TimeoutError, ConnectionError):
				if func_name == "logIn" and self.proxy_pool != None:
					self.proxy = next(self.proxy_pool)
					proxies = {"https": self.proxy}
					self.logger.info(f'Requests with proxy {self.proxy}')
				continue

		self.logger.error(f'Too many tries {self.tries}')
		raise TooManyTriesException(func_name)

	def login(self):
		if self.token:
			self.logger.info('Already logged in')
			return
			
		if self.proxy_pool != None:
			self.proxy = next(self.proxy_pool)
			self.logger.info(f'Requests with proxy {self.proxy}')

		root = self.api_request(func_name='logIn',
								params=('<username></username>'
										'<password></password>'
										f'<AppId>{self.APP_ID}</AppId>'))
		res = root.find('.//return')
		if res.find('status').text == 'OK':
			self.token = res.find('data').text
			self.logger.info('Logged in successfully')
			return

		self.logger.error('Error logging in')
		raise LoginException()

	def logout(self):
		if not self.token:
			self.logger.info('Already logged out')
			return

		root = self.api_request(func_name='logOut', params=f'<handle>{self.token}</handle>')
		res = root.find('.//return')
		if res.find('status').text == 'OK':
			self.logger.info('Logged out successfully')
			self.token = None
			self.proxy = None
			return

		self.logger.error('Error logging out')
		raise LogoutException()

	@BSPlayerDecorators.requires_login
	def search_subtitles(self, video_path, language):
		try:
			file_info = FileInfo(video_path)

			self.logger.info(
				f'Searching subtitles for {video_path} (size={file_info.size} hash={file_info.hash})')
			root = self.api_request(func_name='searchSubtitles', params=(
				f'<handle>{self.token}</handle>'
				f'<movieHash>{file_info.hash}</movieHash>'
				f'<languageId>{language}</languageId>'
				f'<imdbId>*</imdbId>'
			))

			res = root.find('.//return/result')
			if res.find('status').text == 'Not found':
				raise SubtitlesNotFoundException(video_path)
			elif res.find('status').text != 'OK':
				raise UnknownResultError()

			items = root.findall('.//return/data/item')
			subtitles = []
			if items:
				for item in items:
					subtitle = BSPlayerSubtitle.from_element_tree(item)
					if subtitle.validate(): 
						subtitles.append(subtitle)

				if not subtitles:
					raise SubtitlesNotFoundException(video_path)

			self.logger.info('Subtitles found')
			return BSPlayerSubtitleResults(subtitles)
		except SizeTooSmallException:
			self.logger.exception('Probably not a video file')
			raise SubtitlesNotFoundException(video_path)

	@BSPlayerDecorators.requires_login
	def download_by_path(self, video_path, language):
		subtitles = self.search_subtitles(video_path, language)
		video_info = guessit(video_path)
		self.logger.info(f'Downloading subtitle for {video_path}')
		return subtitles.get_qualified(video_info).download(self.timeout, self.proxy, video_path, language)
