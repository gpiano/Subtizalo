import datetime
import subprocess
import sys

import win32serviceutil


def startService(service_name):
    try:
        win32serviceutil.StartService(service_name)
        print "Service started successfully at " + str(datetime.datetime.now()) + " for service: " + service_name
    except:
        print "Service start exception at " + str(datetime.datetime.now()) + " for service: " + service_name

def stopService(service_name):
    try:
        win32serviceutil.StopService(service_name)
        print "Service stopped successfully at " + str(datetime.datetime.now()) + " for service: " + service_name
    except:
        print "Service stop exception at " + str(datetime.datetime.now()) + " for service: " + service_name

def killService(service_name):
    try:
        subprocess.check_call('taskkill /f /fi "services eq %s"' % service_name)
        print "Taskkill executed successfully at " + str(datetime.datetime.now()) + " for service: " + service_name
    except:
        print "Taskkill exception at " + str(datetime.datetime.now()) + " for service: " + service_name

def subtitlesWinServiceManager():
    if len(sys.argv) == 1:
        print('Usage: subtitles-win-service-manager.py [start] [stop] [kill]')
    elif len(sys.argv) == 2:
        task = sys.argv[1]

        if task == 'start': startService("SpanishSubtitlesDownloader")
        elif task == 'stop': stopService("SpanishSubtitlesDownloader")
        elif task == 'kill': killService("SpanishSubtitlesDownloader")

if __name__ == '__main__':
	subtitlesWinServiceManager()
