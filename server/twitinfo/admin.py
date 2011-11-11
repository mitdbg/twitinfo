from server.twitinfo.models import Event
from server.twitinfo.models import Keyword
from server.twitinfo.models import Tweet
from server.twitinfo.models import WordFrequency
from django.contrib import admin

admin.site.register(Event)
admin.site.register(Keyword)
admin.site.register(Tweet)
admin.site.register(WordFrequency)