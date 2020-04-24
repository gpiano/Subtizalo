class SizeTooSmallException(Exception):
    pass


class NotLoggedInException(Exception):
    pass


class TooManyTriesException(Exception):
    pass


class LoginException(Exception):
    pass


class LogoutException(Exception):
    pass


class ParseResponseException(Exception):
    pass


class ServiceUnavailableException(Exception):
    pass


class SubtitlesNotFoundException(Exception):
    def __init__(self, video_path):
        super().__init__(f'Subtitles not found for file: {video_path}')


class UnknownResultException(Exception):
    pass
