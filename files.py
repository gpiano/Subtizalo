import os
import re
import struct
from datetime import datetime
from datetime import timedelta
from exceptions import SizeTooSmallException

from babelfish import Language
from enzyme import MKV


class GetFiles:
    def __init__(self, search_folder, language, age, embedded, logger):
        self.search_folder = search_folder
        self.language = language
        self.age = age
        self.embedded = embedded
        self.logger = logger
        self._qualified_files = []

    def verify_file(self, root, filename, pattern, language):
        full_filename = os.path.join(root, filename)

        if filename.startswith('.'):
            self.logger.info(f'Skipping hidden file {filename}')
            return False
        elif os.path.islink(full_filename):
            self.logger.info(f'Skipping link file {full_filename}')
            return False
        elif not pattern.match(filename):
            return False
        elif self.age is not None and (datetime.utcnow() - datetime.utcfromtimestamp(os.path.getmtime(full_filename)) > timedelta(days=self.age)):
            # Skipping old file without logging
            return False
        else:
            subtitle_filename = full_filename[:-3] + str(language) + ".srt"
            subtitle_file_exists = os.path.exists(subtitle_filename)

            if subtitle_file_exists:
                self.logger.info(f'Skipping externally subtitled file {full_filename}')
                return False
            else:
                return True

    def verify_embedded(self, tracks, language):
        track_match = False
        if tracks:
            for track in tracks:
                if track.language:
                    try:
                        current_language = Language.fromalpha3b(track.language)
                        if current_language == str(language):
                            track_match = True
                            break
                    except:
                        continue
                elif track.name:
                    try:
                        current_language = Language.fromname(track.name)
                        if current_language == str(language):
                            track_match = True
                            break
                    except:
                        continue
        return track_match

    @property
    def qualified_files(self):
        if self._qualified_files:
            return self._qualified_files

        pattern = re.compile(r'.*\.(mkv|mp4|avi)$', re.IGNORECASE)
        language = Language(self.language)

        for root, dirnames, filenames in os.walk(self.search_folder, topdown=True):
            dirnames[:] = [d for d in dirnames if d != "Plex Versions" and not d.startswith('.')]
            for filename in (filename for filename in filenames if self.verify_file(root, filename, pattern, language)):
                full_filename = os.path.join(root, filename)

                embedded_match = False
                if self.embedded:
                    try:
                        extension = os.path.splitext(filename)[1].lower()
                        if extension == '.mkv':
                            with open(full_filename, 'rb') as f:                                
                                mkv = MKV(f)
                                if mkv is not None:
                                    if mkv.audio_tracks and len(mkv.audio_tracks) == 1:
                                        embedded_match = self.verify_embedded(mkv.audio_tracks, language)
                                    if not embedded_match:
                                        embedded_match = self.verify_embedded(mkv.subtitle_tracks, language)
                                        if embedded_match: self.logger.info(f'Internal subtitle found for {full_filename}')    
                                    else:
                                        self.logger.info(f'Internal audio found for {full_filename}')
                    except:
                        pass
                    
                if not embedded_match:
                    self._qualified_files.append(full_filename)

        if self._qualified_files: self.logger.info(f'{len(self._qualified_files)} file(s) to be processed')
        return self._qualified_files

class FileInfo:
    LITTLE_ENDIAN_LONG_LONG = '<q'
    BYTE_SIZE = struct.calcsize(LITTLE_ENDIAN_LONG_LONG)

    def __init__(self, video_path):
        self.path = video_path
        self._file_stat = os.stat(video_path)
        self.size = self._file_stat.st_size
        self._hash = None

    @property
    def hash(self):
        if self._hash:
            return self._hash

        self._hash = self.size
        if self.size < 65536 * 2:
            raise SizeTooSmallException('Size too small')

        with open(self.path, 'rb') as fd:
            for x in range(65536 // self.BYTE_SIZE):
                buff = fd.read(self.BYTE_SIZE)
                (l_value,) = struct.unpack(self.LITTLE_ENDIAN_LONG_LONG, buff)
                self._hash += l_value
                self._hash &= 0xFFFFFFFFFFFFFFFF  # to remain as 64bit number

            fd.seek(max(0, self.size - 65536), 0)
            for x in range(65536 // self.BYTE_SIZE):
                buff = fd.read(self.BYTE_SIZE)
                (l_value,) = struct.unpack(self.LITTLE_ENDIAN_LONG_LONG, buff)
                self._hash += l_value
                self._hash &= 0xFFFFFFFFFFFFFFFF  # to remain as 64bit number

        self._hash = '%016x' % self._hash
        return self._hash
