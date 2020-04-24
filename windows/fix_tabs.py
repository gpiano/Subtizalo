import os
import re

def fixTabs(paths):
    for path in paths:
        for root, dirnames, filenames in os.walk(path):
            for filename in filter(lambda name:re.compile('.*\.(py)$').match(name), filenames):
                full_filename = os.path.join(root, filename)

                with open(full_filename, 'r') as file:
                    filedata = file.read()

                filedata = filedata.replace('    ', '\t')

                with open(full_filename, 'w') as file:
                    file.write(filedata)

if __name__ == "__main__":
    paths = {'C:\SpanishSubtitlesDownloader'}
    fixTabs(paths)