from datetime import datetime

import config as cfg
from download import download
import servicemanager
import win32event
import win32service
import win32serviceutil


class SubtitlesService(win32serviceutil.ServiceFramework):
	_svc_name_ = "SpanishSubtitlesDownloader"
	_svc_display_name_ = "Spanish Subtitles Downloader"
	_svc_description_ = "Spanish Subtitles Downloader"

	def __init__(self, args):
		win32serviceutil.ServiceFramework.__init__(self,args)
		self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)

	def SvcDoRun(self):
		servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
							  servicemanager.PYS_SERVICE_STARTED,
							  (self._svc_name_,''))
		
		rc = None
		while rc != win32event.WAIT_OBJECT_0:
			try:
				download(cfg.SEARCH_FOLDER, age=cfg.AGE, embedded=cfg.EMBEDDED, bsplayer_timeout=cfg.BSPLAYER_TIMEOUT, bsplayer_tries=cfg.BSPLAYER_TRIES, verbose=cfg.VERBOSE, file_log=cfg.FILE_LOG, file_log_folder=cfg.FILE_LOG_FOLDER, use_proxy=cfg.USE_PROXY)
			finally:
				rc = win32event.WaitForSingleObject(self.hWaitStop, cfg.WS_SLEEP * 1000)

	def SvcStop(self):
		self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
		win32event.SetEvent(self.hWaitStop)

if __name__ == '__main__':
	win32serviceutil.HandleCommandLine(SubtitlesService)
