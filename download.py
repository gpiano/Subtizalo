import asyncio
import os
import sys
from argparse import ArgumentParser
from exceptions import (ParseResponseException, ServiceUnavailableException,
						SubtitlesNotFoundException, TooManyTriesException,
						LoginException, LogoutException)
from itertools import cycle

import logbook
from proxybroker import Broker

import config as cfg
from files import GetFiles
from providers.bsplayer import BSPlayer
from providers.subdivx import Subdivx


async def read_queue(queue, proxies):
	while True:
		proxy = await queue.get()
		if proxy is None: 
			break
		proxies.add('%s:%d' % (proxy.host, proxy.port))

def get_proxies(proxies):
	queue = asyncio.Queue()
	broker = Broker(queue)
	tasks = asyncio.gather(broker.find(types=['HTTPS'], limit=10), read_queue(queue, proxies))
	loop = asyncio.get_event_loop()
	loop.run_until_complete(tasks)

def bsplayer_provider(logger, proxy_pool, timeout, tries, video_files, language):
	if video_files:
		try:
			with BSPlayer(logger, proxy_pool, timeout=timeout, tries=tries) as bsplayer:
				for video_path in list(video_files):
					try:
						downloaded = bsplayer.download_by_path(video_path, language=language)	
						if downloaded:
							video_files.remove(video_path)
					except SubtitlesNotFoundException:
						logger.error(f'Subtitles not found for {video_path}')
					except TooManyTriesException:
						logger.error(f'Request failed - too many tries for {video_path}')
					except Exception as ex:
						logger.error(f'{ex} for {video_path}')
					except:
						continue
		except TooManyTriesException:
			logger.error(f'Login failed - too many tries')
		except (LoginException, LogoutException):
			logger.error(f'BS.Player failed')
		except:
			logger.error(f'Unknown error')
		finally:
			if video_files: logger.info(f'{len(video_files)} file(s) still pending to be subtitled')
			logger.name = "General"

def subdivx_provider(logger, proxy_pool, video_files):
	if video_files:
		try:
			with Subdivx(logger, proxy_pool) as subdivx:
				for video_path in list(video_files):
					try:
						downloaded = subdivx.download_by_path(video_path)	
						if downloaded:
							video_files.remove(video_path)
					except SubtitlesNotFoundException:
						logger.error(f'Subtitles not found for {video_path}')
					except (ParseResponseException, ServiceUnavailableException, Exception) as ex:
						logger.error(f'{ex} for {video_path}')
					except:
						continue
		except:
			logger.error(f'Unknown error')
		finally:
			if video_files: logger.info(f'{len(video_files)} file(s) still pending to be subtitled')
			logger.name = "General"	  

def download(search_folder, age=5, embedded=True, language="spa", bsplayer_timeout=5, bsplayer_tries=5, verbose=False, file_log=True, file_log_folder="logs", use_proxy=True):
	logger = logbook.Logger('General')
	if verbose:
		logger.handlers.append(logbook.StreamHandler(sys.stdout, bubble=True))
	if file_log:
		log_file = os.path.join(file_log_folder, 'subtitles.log')
		logger.handlers.append(logbook.TimedRotatingFileHandler(log_file, date_format='%Y-%m-%d'))

	try:
		logger.info(f'Subtitles Downloader started') 

		video_files = GetFiles(search_folder, language=language, age=age, embedded=embedded, logger=logger).qualified_files
		
		if video_files:
			proxy_pool = None
			
			if use_proxy:
				logger.info(f'Getting a list of proxies')
				
				proxies = set()
				get_proxies(proxies)
				proxy_pool = cycle(proxies)

			bsplayer_provider(logger, proxy_pool, bsplayer_timeout, bsplayer_tries, video_files, language)
			subdivx_provider(logger, proxy_pool, video_files)
	except:
		logger.error(f'Error: {sys.exc_info()}')
	else:
		logger.info(f'Subtitles Downloader finished')				

if __name__ == '__main__':
	parser = ArgumentParser()
	parser.add_argument("-f", "--folder", dest="folder", required=False, help="Folder to recursively search subtitles")
	args = parser.parse_args()
	if args.folder is not None:
		cfg.SEARCH_FOLDER = args.folder
		cfg.AGE = None
		cfg.EMBEDDED = True
		cfg.VERBOSE = True

	download(cfg.SEARCH_FOLDER, age=cfg.AGE, embedded=cfg.EMBEDDED, bsplayer_timeout=cfg.BSPLAYER_TIMEOUT, bsplayer_tries=cfg.BSPLAYER_TRIES, verbose=cfg.VERBOSE, file_log=cfg.FILE_LOG, file_log_folder=cfg.FILE_LOG_FOLDER, use_proxy=cfg.USE_PROXY)
