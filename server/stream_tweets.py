import settings
from django.core.management import setup_environ
setup_environ(settings)
from twitinfo.models import Keyword
from threading import Timer

import datetime
import threading
import traceback
import time
import sys
sys.path.append(settings.SSQL_PATH)
from ssql.query_runner import QueryRunner

def query_keywords(rerun_regardless, runner, old_query):
    keywords = Keyword.objects.all().order_by('key_word').values_list('key_word', flat=True)
    new_keywords = []
    for keyword in keywords:
        if keyword.find("'") == -1:
            new_keywords.append(keyword)
        else:
            print 'keyword "%s" contains a single quote---discarding' % (keyword)

    keywords = new_keywords
    filters = "text CONTAINS '%s' OR " * len(keywords)
    filters = filters[:-4] # strip off last " OR "
    query = 'SELECT text, user_id, screen_name, created_at, sentiment(text) AS sent, profile_image_url, location, tweetLatLng("lat") as latitude, tweetLatLng("lng") as longitude FROM twitter INTO TABLE tweets_from_keywords WHERE %s;' % (filters)
    query = query % tuple(keywords)
    if rerun_regardless or (query != old_query):
        if query != old_query:
            print "%s: Running new query '%s'" % (datetime.datetime.now(), query)
        else:
            print "%s: Re-running old query '%s'" % (datetime.datetime.now(), query)
        sys.stdout.flush()
        old_query = query
        runner.run_query(query, True)
    return query

def stream_tweets():
    i = 0
    runner = QueryRunner()
    old_query = None
    while True:
        rerun = ((i % 10) == 0)
        old_query = query_keywords(rerun, runner, old_query)
        time.sleep(30)
        i += 1

# Prints thread stacks if you push ctrl+\
def dumpstacks(signal, frame):
    id2name = dict([(th.ident, th.name) for th in threading.enumerate()])
    code = []
    for threadId, stack in sys._current_frames().items():
        code.append("\n# Thread: %s(%d)" % (id2name[threadId], threadId))
        for filename, lineno, name, line in traceback.extract_stack(stack):
            code.append('File: "%s", line %d, in %s' % (filename, lineno, name))
            if line:
                code.append("  %s" % (line.strip()))
    print "\n".join(code)

import signal
signal.signal(signal.SIGQUIT, dumpstacks)

if __name__ == "__main__":
    stream_tweets()
