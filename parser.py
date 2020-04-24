from bs4 import BeautifulSoup, FeatureNotFound

class ParserBeautifulSoup(BeautifulSoup):
    def __init__(self, markup, parsers, **kwargs):
        if set(parsers).intersection({'fast', 'permissive', 'strict', 'xml', 'html', 'html5'}):
            raise ValueError('Features not allowed, only parser names')

        if 'features' in kwargs:
            raise ValueError('Cannot use features kwarg')
        if 'builder' in kwargs:
            raise ValueError('Cannot use builder kwarg')

        for parser in parsers:
            try:
                super(ParserBeautifulSoup, self).__init__(markup, parser, **kwargs)
                return
            except FeatureNotFound:
                pass

        raise FeatureNotFound