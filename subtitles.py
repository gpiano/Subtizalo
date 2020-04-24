import gzip
import io
import os
import re
import zipfile
from exceptions import (ParseResponseException, ServiceUnavailableException,
						SubtitlesNotFoundException)
from parser import ParserBeautifulSoup

import rarfile
import requests
from babelfish import Language
from guessit import guessit

from tree import ElementTreeObject


class BSPlayerSubtitle(ElementTreeObject):
	__properties__ = {'subID': 'id', 'subSize': 'size', 'subDownloadLink': 'url', 'subLang': 'language',
					  'subName': 'name', 'subFormat': 'format', 'subHash': 'hash', 'subRating': 'rating'}
	__types__ = {'size': int, 'rating': int}
	__repr_format__ = '<{name}: {language} ({rating})>'

	def validate(self):
		return self.format == "srt"

	def download(self, timeout, proxy, video_path, language):
		if timeout is None or video_path is None or language is None:
			raise TypeError("Invalid download parameters")

		headers = {'User-Agent': 'Mozilla/4.0 (compatible; Synapse)', 'Content-Length': '0'}

		proxies = None
		if proxy != None:
			proxies = {"https": proxy}

		res = requests.get(self.url, headers=headers, timeout=timeout, proxies=proxies)

		if res.content == '500':
			raise Exception('Error while downloading subtitles')

		language = Language(language)
		subtitle_filename = video_path[:-3] + str(language) + ".srt"
		with gzip.GzipFile(fileobj=io.BytesIO(res.content)) as gf:
			with open(subtitle_filename, 'wb') as f:
				f.write(gf.read())

		return True

class SubdivxSubtitle():
	def __init__(self, page_link, description, title):
		self.page_link = page_link
		self.description = description
		self.title = title

	def check_response(self, response):
		if response.status_code != 200:
			raise ServiceUnavailableException('Bad status code: ' + str(response.status_code))

	def get_download_link(self, session, timeout, proxies):		
		response = session.get(self.page_link, timeout=timeout, proxies=proxies)
		self.check_response(response)

		try:
			page_soup = ParserBeautifulSoup(response.content.decode('iso-8859-1', 'ignore'), ['lxml', 'html.parser'])
			links_soup = page_soup.find_all("a", {'class': 'link1'})
			for link_soup in links_soup:
				if 'bajar' in link_soup['href']:
					return link_soup['href']
		except Exception as e:
			raise ParseResponseException('Error parsing download link: ' + str(e))
		raise ParseResponseException('Download link not found')

	def get_archive(self, content):
		archive_stream = io.BytesIO(content)
		if rarfile.is_rarfile(archive_stream):
			archive = rarfile.RarFile(archive_stream)
		elif zipfile.is_zipfile(archive_stream):
			archive = zipfile.ZipFile(archive_stream)
		else:
			raise ParseResponseException('Unsupported compressed format')

		return archive

	def contains_forced(self, filename):
		return re.search('(FORZADO|FORCED)', filename, re.IGNORECASE) is not None

	def contains_release_group(self, filename, release_group):
		return re.search(re.escape(release_group), filename, re.IGNORECASE) is not None

	def get_subtitle_from_archive(self, archive, release_group):
		result_name = None
		for name in archive.namelist():
			if os.path.split(name)[-1].startswith('.'):
				continue

			if not name.lower().endswith('.srt'):
				continue

			if self.contains_forced(name):
				continue

			result_name = name 
			if self.contains_release_group(name, release_group):
				break	

		if result_name:
			return archive.read(result_name)

		raise ParseResponseException('Subtitle in the compressed file not found')

	def fix_line_ending(self, content):
		return content.replace(b'\r\n', b'\n')

	def download(self, session, timeout, proxy, video_path, video_info):
		if session is None or timeout is None or video_path is None:
			raise TypeError("Invalid download parameters")

		proxies = None
		if proxy != None:
			proxies = {"https": proxy}
			
		download_link = self.get_download_link(session, timeout, proxies)
		response = session.get(download_link, headers={'Referer': self.page_link}, timeout=timeout, proxies=proxies)
		self.check_response(response)

		archive = self.get_archive(response.content)
		release_group = video_info.get("release_group")
		subtitle_content = self.get_subtitle_from_archive(archive, release_group)
		content = self.fix_line_ending(subtitle_content)
		
		subtitle_filename = video_path[:-3] + "es.srt"
		with open(subtitle_filename, 'wb') as f:
			f.write(content)

		return True

class BSPlayerSubtitleResults:
	def __init__(self, subtitles):
		self.subtitles = subtitles

	def get_qualified(self, video_info):
		subtitles_sorted = sorted(self.subtitles, key=lambda s: s.rating, reverse=True)
		qualified_subtitle = subtitles_sorted[0]

		release_group = video_info.get("release_group")
		if release_group is not None:
			current_release_group = release_group.split("[")	
			if current_release_group is not None:
				for item in subtitles_sorted:
					remote_subtitle_info = guessit(item.name)
					if remote_subtitle_info.get("release_group") is not None:
						remote_release_group = remote_subtitle_info.get("release_group").split("[")
						if current_release_group[0].lower() == remote_release_group[0].lower():
							qualified_subtitle = item
							break

		return qualified_subtitle
		
	def __len__(self):
		return len(self.size)

	def __getitem__(self, item):
		return self.subtitles[item]

	def __repr__(self):
		return f'<{self.__class__.__name__}: {len(self)}>'

class SubdivxSubtitleResults:
	def __init__(self, subtitles):
		self.subtitles = subtitles

	def get_qualified(self, video_info):
		qualified_subtitle = None
		release_group = video_info.get("release_group")
		if release_group is not None:
			current_release_group = release_group.split("[")	
			if current_release_group is not None:
				for item in self.subtitles:
					found = re.search(re.escape(current_release_group[0]), item.description, re.IGNORECASE) is not None
					if found:
						qualified_subtitle = item
						break
		
		if qualified_subtitle:
			return qualified_subtitle

		raise SubtitlesNotFoundException('Qualified subtitle not found')
