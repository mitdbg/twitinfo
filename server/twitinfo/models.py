from django.db import models
from django import forms

class Tweet(models.Model):
    id = models.AutoField(primary_key=True, db_column="__id")
    tweet = models.TextField(db_column="text")
    user_id = models.IntegerField(default=0)
    screen_name = models.TextField(default="")
    created_at = models.DateTimeField('created date', db_index=True)
    sentiment = models.FloatField(db_column='sent')
    profile_image_url = models.TextField()
    location = models.TextField(null=True)
    latitude = models.FloatField(null=True)
    longitude = models.FloatField(null=True)

    class Meta:
        db_table = 'tweets_from_keywords'
    def __unicode__(self):
        return self.tweet

class Keyword(models.Model):
    key_word = models.CharField(max_length=200, unique=True)
    tweets = models.ManyToManyField(Tweet)
    max_indexed = models.IntegerField(default=-1)
    
    
    @staticmethod   
    def normalize_keywords(keywords):
        """
            takes in a comma separated string of keywords and returns a list of normalized keywords.
        """
        list_keywords=[]
        k=keywords.split(',')
        for key in k:
            filtered_key = Keyword.normalize(key)
            list_keywords.append(filtered_key)
        return list_keywords

    @staticmethod
    def normalize(kw):
        return (' '.join(kw.split())).lower()
        
    def __unicode__(self):
        return self.key_word

    
class Event(models.Model):
    featured = models.BooleanField(default=False)
    name = models.CharField(max_length=200)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    keywords = models.ManyToManyField(Keyword)
    children = models.ManyToManyField("self", symmetrical=False, related_name='parents', blank=True)
    def __unicode__(self):
        return self.name
    
    @staticmethod   
    def normalize_name(name):
        return (' '.join(name.split())).lower()
    

class WordFrequency(models.Model):
    word = models.CharField(max_length=300)
    idf = models.FloatField()
