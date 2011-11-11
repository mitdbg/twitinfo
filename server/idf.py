from django.core.management import setup_environ
import settings
setup_environ(settings)
from twitinfo.models import Event,Tweet,Keyword,WordFrequency
from datetime import datetime,timedelta
import os
import math

# Read NUM_TWEETS random tweets, and compute the IDF of the terms in those
# tweets using a map/reduce pattern.  Save the top TOP_WORDS words (with 
# the smallest IDF) as WordFrequency objects.
NUM_TWEETS = 10000
TOP_WORDS = 1000

def map():
    i=0
    count=0
    
    fw = open('mapreduce.txt','w')
    tweets=Tweet.objects.all().order_by('?')[:NUM_TWEETS]
    for tweet in tweets:
        repeat = set()
        count += 1
        words = tweet.tweet.encode('utf8').lower().split()
        for word in words:
            if word not in repeat:
                repeat.add(word)
                fw.write(word + '\n')

    total_tweets=count      
    fw.close() 
    reduce(total_tweets)          


def reduce(total_tweets):
    os.system("sort mapreduce.txt > sorted.txt")
    words = open('sorted.txt','r')
    fw = open('sorted_count.txt','w')
    list_words = []
    """
    for word in words:
        if word in list_words:
            count += 1
        else:
            if len(list_words) != 0:
                b=list_words[0].split('\n')
                i=total_tweets/float(count+1)
                idf=math.log(i,2)
                fw.write(b[0]+' '+str(idf) + '\n')
            list_words=[]
            list_words.append(word)
            count=1
    """
    active_word = None
    for word in words:
        word = word.strip()
        if word == active_word:
            count += 1
        else:
            if active_word != None:
                idf = math.log(total_tweets/float(count+1), 2)
                fw.write(active_word + ' ' + str(idf) + '\n')
            active_word = word
            count = 1
    fw.close()
    os.system("sort -n -k 2 sorted_count.txt > bycount.txt")   
    add_to_database()

def add_to_database():
    WordFrequency.objects.all().delete()
    wordcounts = open('bycount.txt','r')
    count = 0
    for line in wordcounts:
        words=line.split()
        word = words[0]
        idf = float(words[1])
        try:
            w = WordFrequency.objects.get(word = word)
            w.idf = idf
            w.save()
        except:
            w = WordFrequency(word = word,idf = idf)
            w.save()
        count += 1
        if count == TOP_WORDS:
            break

map()
