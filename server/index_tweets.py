import settings
from django.core.management import setup_environ
setup_environ(settings)

from django.db import transaction
from twitinfo.models import Keyword, Tweet
import datetime
import threading
import traceback
import time
import sys
import settings

@transaction.commit_manually
def index_tweets():
    # wait 5 seconds unless we've actually indexed something this time
    # around, in which case the wait time will be 0 before we call this
    # function again (see wait_time = 0 below).
    wait_time = 5

    # Make max_indexed->keyword sorted mapping
    kws = Keyword.objects.order_by('max_indexed')
    sorted_kws = []
    indexed_kws = {}
    index_group = []
    index_val = kws[0].max_indexed
    for kw in kws:
        if kw.max_indexed != index_val:
            sorted_kws.append({'index_val': index_val, 'index_group': index_group})
            index_val = kw.max_indexed
            index_group = []
        index_group.append(kw)
        indexed_kws[Keyword.normalize(kw.key_word)] = kw
    sorted_kws.append({'index_val': index_val, 'index_group': index_group})
    
    # Get up to 1000 tweets >= min keyword state
    # Loop through tweets, adding keywords to a set from the max_indexed
    # mapping
    curloc = 0
    tweets = Tweet.objects.filter(id__gte = sorted_kws[0]['index_val']).order_by('id')[:1000]
    tweets = list(tweets)
    active_kws = set()
    for tweet in tweets:
        while curloc >= 0 and tweet.id > sorted_kws[curloc]['index_val']:
            for kw in sorted_kws[curloc]['index_group']:
                active_kws.add(Keyword.normalize(kw.key_word))
            curloc += 1
            if curloc >= len(sorted_kws):
                curloc = -1
        matches = active_kws.intersection(tweet.tweet.lower().split())
        for match in matches:
            kw = indexed_kws[match]
            kw.tweets.add(tweet)
    
    if len(tweets) > 0:
        highest_tweet = tweets[-1].id
        actually_indexed = False
        for kw in kws:
            if kw.max_indexed != highest_tweet:
                kw.max_indexed = highest_tweet
                kw.save()
                actually_indexed = True
        if actually_indexed:
            wait_time = 0
            print "%s: Indexed tweets in range [%d, %d]" % (datetime.datetime.now(), tweets[0].id, highest_tweet)
            sys.stdout.flush()
    try:
        transaction.commit()
    except Exception,e:
        print e

    return wait_time

def index_loop():
    counter = 0
    while True:
        wait_time = index_tweets()
        time.sleep(wait_time)
        counter += 1
        if counter == 100:
            print "Ending indexer to avoid memory leaks"
            break

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
    index_loop()
