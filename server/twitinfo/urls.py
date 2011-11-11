from django.conf.urls.defaults import *

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('server.twitinfo.views',
    (r'^$', 'twitinfo'),
    (r'^results', 'search_results'),
    (r'^detail/(?P<event_id>\d+)/$', 'event_details'),
    (r'^create_event/$', 'create_event'),
    (r'^detail/create_graph/(?P<event_id>\d+)/$', 'create_graph'),
    (r'^detail/create_piChart/(?P<event_id>\d+)/$', 'create_pieChart'),
    (r'^detail/create_map/(?P<event_id>\d+)/$', 'create_map'),
    (r'^display_tweets/(?P<event_id>\d+)/$', 'display_tweets'),
    (r'^display_links/(?P<event_id>\d+)/$', 'display_links'),
)
