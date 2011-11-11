from django import forms
from django.shortcuts import get_object_or_404, render_to_response
from django.http import HttpResponseRedirect, HttpResponse
from django.core.cache import cache
from django.core.context_processors import csrf
from django.core.urlresolvers import reverse
from django.db.models import Avg, Max, Min, Count, Sum, F
from django.template import RequestContext, Context, Template, loader
from django.views.decorators.cache import cache_page
from server.twitinfo.models import Event,Tweet,Keyword,WordFrequency
from datetime import datetime,timedelta
from operator import itemgetter
import itertools
import json
import nltk
import re
import random
import sys
import settings
sys.path.append(settings.SSQL_PATH)
from ssql.builtin_functions import MeanOutliers

NUM_TWEETS = 20 # total tweets to display
NUM_LINKS = 3 # total top links to display
URL_REGEX = re.compile("http\:\/\/\S+")
CACHE_SECONDS = 864000

def twitinfo(request):
    featured = Event.objects.filter(featured = True)
    return render_to_response('twitinfo/twitinfo.html', {"featured":featured})
       
def search_results(request):
    search = Event.normalize_name(request.GET['query'])
    events = Event.objects.filter(name = search)
    events_from_keywords = Event.objects.filter(keywords__key_word=search)
    total_events=itertools.chain(events,events_from_keywords)
    total_events=list(total_events)
    if len(total_events)==0:
        return render_to_response('twitinfo/results.html', {'error':'Sorry, the keyword you searched for does not exist.'},
                                 context_instance=RequestContext(request))
    else:
        return render_to_response('twitinfo/results.html', {'events':total_events},
                               context_instance=RequestContext(request))
                                   
def event_details(request,event_id):
    try:
       keys=[]
       event = Event.objects.get(pk=event_id)
       keywords = Keyword.objects.filter(event=event_id).values_list('key_word', flat=True)
       keys=", ".join(keywords)
    except Event.DoesNotExist:
        return render_to_response('twitinfo/details.html', {'error':'Event does not exit!'},
                                 context_instance=RequestContext(request))
  
    return render_to_response('twitinfo/details.html', {'event':event,'keywords':keys},
                                  context_instance=RequestContext(request))

class TweetDateForm(forms.Form):
    start_date = forms.DateTimeField(input_formats=["%Y-%m-%d %H:%M"],required=False)
    end_date = forms.DateTimeField(input_formats=["%Y-%m-%d %H:%M"],required=False)
    words = forms.CharField(required=False)

def display_tweets(request,event_id):
    key = request.get_full_path()
    print "fp: %s" % key
    resp_string = cache.get(key)
    if resp_string == None:
        print "no cache"
        resp_string = display_tweets_impl(request, event_id)
        cache.set(key, resp_string, CACHE_SECONDS)
    print "after getting data"
    return HttpResponse(resp_string)

def display_tweets_impl(request,event_id):
    try:
       print "before"
       event = Event.objects.get(pk=event_id)
       print "uh"
    except Event.DoesNotExist:
        return render_to_response('twitinfo/display_tweets.html', {'error':'Event does not exit!'},
                                 context_instance=RequestContext(request))
    tweets = Tweet.objects.filter(keyword__event=event_id)
    print "generated tweets query"
    form = TweetDateForm(request.REQUEST)
    if form.is_valid():
        print "getting date data"
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
        start_date = start_date if start_date != None else event.start_date
        end_date = end_date if end_date != None else event.end_date
        if start_date != None:
            tweets = tweets.filter(created_at__gte = start_date)
        if end_date != None:
            tweets = tweets.filter(created_at__lte = end_date)
        tweets = tweets.order_by("created_at")#+
        words = form.cleaned_data['words']
        if len(words) == 0:
            print "no words"
            tweets = tweets[:NUM_TWEETS]
        else:
            print "splitting tweets"
            words = words.split(",")
            matched_tweets = []
            already_tweets = set()
            for tweet in tweets[:500]:
                count = 0
                text = tweet.tweet.lower()
                if "rt" in text:
                    count -= 2
                text = URL_REGEX.sub("WEBSITE", text)
                if text not in already_tweets:
                    for word in words:
                        if word in text:
                            count += 1
                    matched_tweets.append((tweet, count))
                    already_tweets.add(text)
            matched_tweets.sort(cmp=lambda a,b: cmp(b[1],a[1]))
            tweets = [t[0] for t in matched_tweets[:min(NUM_TWEETS,len(matched_tweets))]]
        t = loader.get_template('twitinfo/display_tweets.html')
        print len(tweets)
        resp_string = t.render(Context({'tweets': tweets,'event':event}))
        return resp_string

def display_links(request,event_id):
    key = request.get_full_path()
    resp_string = cache.get(key)
    if resp_string == None:
        resp_string = display_links_impl(request, event_id)
        cache.set(key, resp_string, CACHE_SECONDS)
    return HttpResponse(resp_string)

def display_links_impl(request,event_id):
    try:
       event = Event.objects.get(pk=event_id)
    except Event.DoesNotExist:
        return 'Event does not exit!'
    tweets = Tweet.objects.filter(keyword__event=event_id)

    form = TweetDateForm(request.REQUEST)
    if form.is_valid():
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
        start_date = start_date if start_date != None else event.start_date
        end_date = end_date if end_date != None else event.end_date
        if start_date != None:
            tweets = tweets.filter(created_at__gte = start_date)
        if end_date != None:
            tweets = tweets.filter(created_at__lte = end_date)
        tweets = tweets.order_by("created_at")#+
        links = {}
        for tweet in tweets[:500]:
            text = tweet.tweet
            incr = 1
            if "RT" in text:
                incr = .5
            for match in URL_REGEX.findall(text):
                count = links.get(match, 0.0)
                count += incr
                links[match] = count
        linkcounts = links.items()
        linkcounts.sort(key = itemgetter(1), reverse = True)
        displaylinks = []
        for i in range(0, min(len(linkcounts), NUM_LINKS)):
            if linkcounts[i][1] > 2.5:
                displaylinks.append((linkcounts[i][0], int(linkcounts[i][1])))
        t = loader.get_template('twitinfo/display_links.html')
        resp_string = t.render(Context({'links': displaylinks}))
        return resp_string
    
class EventForm(forms.Form):
    title=forms.CharField(max_length=100)
    key_words = forms.CharField()
    start_date = forms.DateTimeField(input_formats=["%Y-%m-%d %H:%M"],required=False)
    end_date = forms.DateTimeField(input_formats=["%Y-%m-%d %H:%M"],required=False)
    parent_id = forms.IntegerField(widget=forms.HiddenInput,required=False)
    

def create_event(request):
   if request.method == 'POST': # If the form has been submitted...
       form = EventForm(request.POST) # A form bound to the POST data
       if form.is_valid():
           name = form.cleaned_data['title']
           name = Event.normalize_name(name)
           key_words = form.cleaned_data['key_words']
           list_keywords = Keyword.normalize_keywords(key_words)
           keyobjs=[]
           for key in list_keywords:
               try:
                   fkeyword = Keyword.objects.get(key_word = key)
               except Keyword.DoesNotExist:
                   fkeyword = Keyword(key_word = key)
                   fkeyword.save() 
               keyobjs.append(fkeyword)  
           
           e = Event(name = name,start_date = None,end_date = None)
           try:
               e.start_date = form.cleaned_data['start_date']
           except:
               pass
           try:
               e.end_date = form.cleaned_data['end_date']
           except:
               pass
           e.save()
           e.keywords = keyobjs
           try:
               parent = form.cleaned_data['parent_id']
               parent_event = Event.objects.get(id=parent)
               parent_event.children.add(e)
               cache.delete("graph" + str(parent)) # clear parent view to include child
           except Event.DoesNotExist:
               pass
           return HttpResponseRedirect('detail/%d' % (e.id)) # Redirect after POST
   else:
       # initialize the form with a set of values that are passed in as data. If there are no initial values,initialize an empty form.
       try:
           parent_id=request.GET["parent_id"]
           keywords=request.GET["keywords"]
           sd=request.GET["start_date"]
           ed=request.GET["end_date"]
           data={'start_date':sd,'end_date':ed,'key_words':keywords,'parent_id':parent_id,'title':" "}
           form = EventForm(data) 
       except:
           form = EventForm()
   return render_to_response('twitinfo/create_event.html', {'form': form}, context_instance=RequestContext(request))    
   

def find_end_dates(tweets,list_peaks):
    i=0
    k=0
    
    if len(list_peaks) > 0:
        while(i<len(list_peaks) and i+1<len(list_peaks)):
            for j in range(len(tweets)):
                if(list_peaks[i]["start_date"]==tweets[j]['date']):
                    k=j+1
                    break
            while(k<len(tweets)):
                    if(list_peaks[i+1]['start_date']==tweets[k]['date'] or tweets[k]['num_tweets']<=list_peaks[i]["start_freq"] or k==len(tweets)-1):
                        end_date=tweets[k]['date']
                        list_peaks[i]["end_date"]=end_date
                        break
                    k+=1
            i+=1
        for l in range(len(tweets)):
                if(list_peaks[len(list_peaks)-1]["start_date"]==tweets[l]['date']):
                    k=l+1
                    break
                    
        while(k<len(tweets)):
                    if( tweets[k]['num_tweets']<=list_peaks[len(list_peaks)-1]["start_freq"] or k==(len(tweets)-1)):
                        end_date=tweets[k]['date']
                        list_peaks[len(list_peaks)-1]["end_date"]=end_date
                    k+=1
    return list_peaks  

def words_by_tfidf(dic, keywords):
    freq_words = WordFrequency.objects.filter(word__in = dic.iterkeys()).values_list('word', 'idf')

    # multiply by -1*idf if it exists in the idf list.  record the largest
    # idf witnessed
    maxidf = 0
    for word, idf in freq_words:
        if word in dic:
            dic[word] *= -1 * idf
            if idf > maxidf:
                maxidf = idf
    
    # for all idfs which existed, make the tfidf positive again.
    # for all already-positive idfs (which didn't have an idf for this
    # word), multiply by 10 more than the largest idf in the list.
    maxidf += 10
    for word, idf in dic.items():
        if idf < 0:
            dic[word] *= -1
        else:
            dic[word] *= maxidf

    words = dic.keys() 
    words.sort(cmp=lambda a,b: cmp(dic[b],dic[a]))
    return words

def find_max_terms(tweets, keywords):
     total_freq=0
     words_dict={}
     stopwords = set(nltk.corpus.stopwords.words('english'))
     stopwords.add("rt")
     for tweet in tweets:    
         text = tweet.tweet
         tweet_text=text.lower().replace("'","").split()
         for word in tweet_text:
             if word in stopwords:
                 continue
             if words_dict.has_key(word):
                 words_dict[word]+=1
             else:
                 words_dict[word]=1 
     
     return words_by_tfidf(words_dict, keywords)
 
def annotate_peaks(peaks,tweets,event_id,keywords):
    list_keywords = ", ".join(keywords) 
    for peak in peaks:
        sdt = convert_date(peak['start_date'])
        edt = convert_date(peak['end_date'])
        t=Tweet.objects.filter(keyword__event=event_id).filter(created_at__gte=sdt).filter(created_at__lte=edt)
        sorted_list=find_max_terms(t, keywords)
        for tweet in tweets:
            if peak['peak_date']==tweet['date']:
                tweet['title']="'" +", ".join(sorted_list[:5])+"'"
                
                tweet['data']={'event':event_id,'keywords':list_keywords,'start_date':sdt.strftime("%Y-%m-%d %H:%M"),'end_date':edt.strftime("%Y-%m-%d %H:%M")}          
    return tweets
        

def convert_date(date):
    d=date.split(',')
    d=map(int , d)
    dt=datetime(*d)
    return dt
       
def create_graph(request,event_id):
    key = "graph" + event_id
    resp_string = cache.get(key)
    if resp_string == None:
        resp_string = create_graph_impl(request, event_id)
        cache.set(key, resp_string, CACHE_SECONDS)
    resp_string = request.GET["jsoncallback"] + resp_string
    return HttpResponse(resp_string)

def create_graph_impl(request, event_id):
    e = Event.objects.get(id=event_id)
    sdate = e.start_date
    edate = e.end_date
    tweets = Tweet.objects.filter(keyword__event = event_id)
    
    if sdate == None:
        sdate=tweets.order_by('created_at')[0].created_at
    if edate == None:
        edate=tweets.order_by('-created_at')[0].created_at
        
    tdelta=(edate-sdate)
    total_sec=tdelta.seconds + tdelta.days * 24 *3600
    total_min=total_sec / 60.0
    total_hours=total_min / 60.0
    
    if total_min <= 1440:
        td=timedelta(minutes=1)
        sec_divisor = 60
        stf = {"date": ('%Y,%m,%d,%H,%M'),"d": 'new Date(%Y,%m-1,%d,%H,%M)'}
        if settings.DATABASES['default']['ENGINE'] == 'postgresql_psycopg2':
            select_data = {"d": "to_char(created_at, 'ne\"w\" \"D\"ate(YYYY,MM-1,DD, HH24,MI)')" , "date":"to_char(created_at, 'YYYY,MM,DD,HH24,MI')"}
        else:
            select_data = {"d": "strftime('new Date(%%Y,%%m-1,%%d,%%H,%%M)', created_at)" , "date":"strftime(('%%Y,%%m,%%d,%%H,%%M') , created_at)"}
      
    elif total_hours <= 2016: # 24 hours x 28 days x 3 = about 3 months
        td=timedelta(hours=1)
        sec_divisor = 3600
        stf = {"date": ('%Y,%m,%d,%H'),"d": 'new Date(%Y,%m-1,%d,%H)'}
        if settings.DATABASES['default']['ENGINE'] == 'postgresql_psycopg2':
            select_data = {"d": "to_char(created_at, 'ne\"w\" \"D\"ate(YYYY,MM-1,DD,HH24)')" , "date":"to_char(created_at, 'YYYY,MM,DD,HH24')"}
        else:
            select_data = {"d": "strftime('new Date(%%Y,%%m-1,%%d,%%H)', created_at)" , "date":"strftime(('%%Y,%%m,%%d,%%H') , created_at)"}
    else:
        td=timedelta(days=1)
        sec_divisor = 86400
        stf = {"date": ('%Y,%m,%d'),"d": 'new Date(%Y,%m-1,%d)'}
        if settings.DATABASES['default']['ENGINE'] == 'postgresql_psycopg2':
            select_data = {"d": "to_char(created_at, 'ne\"w\" \"D\"ate(YYYY,MM-1,DD)')" , "date":"to_char(created_at, 'YYYY,MM,DD')"}
        else:
            select_data = {"d": "strftime('new Date(%%Y,%%m-1,%%d)', created_at)" , "date":"strftime(('%%Y,%%m,%%d') , created_at)"}

    
    tweets = tweets.filter(created_at__gte = sdate).filter(created_at__lte = edate).extra(select = select_data).values('d','date').annotate(num_tweets = Count('tweet')).order_by('date')
    tweets=list(tweets)
    
    i = 1
    detector = MeanOutliers.factory()
    list_peaks = []
    # loop through the tweets and detect a peak based on mean deviation function provided. save the start date
    # and the date of the peak in a dictionary.  save each peak in list_peaks.
    while i < len(tweets):
        tweets[0]['title'] = 'null'
        tweets[0]['data'] = 'null'
        # sd_p=tweets[i-1]['date'].split(',')
        # sd_p=map(int , sd_p)
        # sdt_p=datetime(*sd_p)
        sdt_p=convert_date(tweets[i-1]['date'])
        sd_n=tweets[i]['date'].split(',')
        sd_n=map(int , sd_n)
        sdt_n=datetime(*sd_n)
        delta_d=(sdt_n-sdt_p)
        delta_d = (delta_d.seconds + delta_d.days * 24 *3600)/sec_divisor  
    
        count=0
        if delta_d != 1:
            j=0
            while(j<delta_d-1):
                insert_tweet={'title':'null','num_tweets':0,'data':'null','children':'null'}
                sdt_p = sdt_p+td    
                insert_tweet['date']=sdt_p.strftime(stf['date'])
                insert_tweet['d']=sdt_p.strftime(stf['d'])
                tweets.insert(i+j,insert_tweet)
                j+=1
       
        current_val = tweets[i]['num_tweets']
        previous_val = tweets[i-1]['num_tweets']
        mdiv = detector(None,tweets[i]['num_tweets'], 1)
        if mdiv > 2.0 and current_val > previous_val and current_val > 10:
            start_freq = previous_val 
            start_date = tweets[i-1]['date']
            # once a peak is detected, keep climbing up the peak until the maximum is reached. store the peak date and keep
            # running the mdiv function on each value because it is requires previous values to calculate the mean.
            while(current_val > previous_val):
                  tweets[i]['title'] = 'null'
                  tweets[i]['data'] = 'null'
                  if i+1<len(tweets):
                      i+=1
                      mdiv = detector(None,tweets[i]['num_tweets'], 1)
                      current_val = tweets[i]['num_tweets']
                      previous_val = tweets[i-1]['num_tweets'] 
                      peak_date = tweets[i-1]['date']  
                  else:
                      peak_date = tweets[i]['date']
                      i+=1
                      break
            d = {"start_date":start_date,"start_freq":start_freq ,"peak_date":peak_date}
            list_peaks.append(d)
        else:
            tweets[i]['title'] = 'null'
            tweets[i]['data'] = 'null'
            i+=1

    keywords = Keyword.objects.filter(event__id = event_id)
    words = [kw.key_word for kw in keywords]
    peaks = find_end_dates(tweets,list_peaks)
    
    tweets = annotate_peaks(peaks,tweets,event_id,words)
    try:
        children = e.children.order_by('start_date')
        tweets = peak_child_detection(children,list_peaks,tweets)
    except:
        tweets = tweets
    t = loader.get_template('twitinfo/create_graph.html')
    resp_string = t.render(Context({ 'tweets': tweets }))
    return resp_string

def peak_child_detection(children,list_peaks,tweets):
    list_overlaps=[]
    i=0
    savej=0
    count=0
    while(i<len(children)):
        j=savej
        while(j<len(list_peaks)):
            
            if ((children[i].start_date >= convert_date(list_peaks[j]['start_date']) and children[i].start_date <= convert_date(list_peaks[j]['end_date'])) or
                (children[i].end_date >=convert_date(list_peaks[j]['start_date'])  and children[i].end_date<=convert_date(list_peaks[j]['end_date'])) or
                    (convert_date(list_peaks[j]['start_date'])>=children[i].start_date and convert_date(list_peaks[j]['start_date'])<=children[i].end_date) or
                    (convert_date(list_peaks[j]['end_date']) >= children[i].start_date and convert_date(list_peaks[j]['end_date'])<=children[i].end_date)):
                   
                    if(count==1):
                        savej=j-1
                    
                    if list_peaks[j].has_key("children"):   
                        list_peaks[j]["children"].append(children[i])
                    else:
                        list_peaks[j]["children"]=[children[i]] 
                    
                    j+=1
                
            elif(convert_date(list_peaks[j]['start_date']) > children[i].end_date):
                j=savej
                break
            elif(convert_date(list_peaks[j]['end_date']) < children[i].start_date):
                count+=1
                j+=1
            
        i+=1
       
    j=0
    for peak in list_peaks:
        if peak.has_key("children"):
            while(j<len(tweets)):
                if convert_date(tweets[j]['date'])==convert_date(peak["peak_date"]):
                    tweets[j]['children']=peak["children"]
                    j+=1
                    break
                else:
                    tweets[j]['children'] = None
         
                j+=1
      
  
    while(j<len(tweets)):
        tweets[j]['children'] = None
        j+=1
    
    return tweets

def create_pieChart(request, event_id):
    form = TweetDateForm(request.REQUEST)
    if form.is_valid():
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
    key = "pie" + event_id 
    if start_date != None:
        key += str(start_date)
    if end_date != None:
        key += str(end_date)
    key = "".join(key.split())
    resp_string = cache.get(key)
    if resp_string == None:
        resp_string = create_pieChart_impl(request, event_id, start_date, end_date)
        cache.set(key, resp_string, CACHE_SECONDS)
    resp_string = request.GET["jsoncallback"] + resp_string
    return HttpResponse(resp_string)

def create_pieChart_impl(request, event_id, start_date, end_date):
    event = Event.objects.get(pk=event_id)
    tweets = Tweet.objects.filter(keyword__event=event)
    start_date = start_date if start_date != None else event.start_date
    end_date = end_date if end_date != None else event.end_date
    if start_date != None:
        tweets = tweets.filter(created_at__gte = start_date)
    if end_date != None:
        tweets = tweets.filter(created_at__lte = end_date)
    sum_positive = tweets.filter(sentiment__gt=0.0).aggregate(pos_tweets=Sum('sentiment'))
    sum_positive['pos_tweets'] = round(sum_positive['pos_tweets'] if sum_positive['pos_tweets']!=None else 0)
    sum_negative = tweets.filter(sentiment__lt=0.0).aggregate(neg_tweets=Sum('sentiment'))
    sum_negative['neg_tweets'] = round(sum_negative['neg_tweets'] if sum_negative['neg_tweets']!=None else 0)*-1.0
    
    sums=[]
    sums.append(sum_positive)
    sums.append(sum_negative)
    rows = []
    cols = [{'id': 'sentiment','label':'SENTIMENT','type': 'string'},{'id': 'frequency','label':'FREQUENCY' ,'type': 'number'}]
 
    for val in sums:
        if "pos_tweets" in val:
            p ='positive'
            rows.append( {'c':[ {'v':p},{'v':val['pos_tweets']} ] } )
        else:
            p='negative'
            rows.append( {'c':[ {'v':p},{'v':val['neg_tweets']} ] } )
              
    data={'cols':cols,'rows':rows}
    return "("+json.dumps(data)+");"

def create_map(request, event_id):
    form = TweetDateForm(request.REQUEST)
    if form.is_valid():
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
    key = "map" + event_id 
    if start_date != None:
        key += str(start_date)
    if end_date != None:
        key += str(end_date)
    key = "".join(key.split())
    resp_string = cache.get(key)
    if resp_string == None:
        resp_string = create_map_impl(request, event_id, start_date, end_date)
        cache.set(key, resp_string, CACHE_SECONDS)
    resp_string = request.GET["jsoncallback"] + resp_string
    return HttpResponse(resp_string)

def create_map_impl(request, event_id, start_date, end_date):
    event = Event.objects.get(pk=event_id)
    tweets = Tweet.objects.filter(keyword__event=event)
    start_date = start_date if start_date != None else event.start_date
    end_date = end_date if end_date != None else event.end_date
    if start_date != None:
        tweets = tweets.filter(created_at__gte = start_date)
    if end_date != None:
        tweets = tweets.filter(created_at__lte = end_date)
    tweets = tweets.filter(latitude__isnull = False)
    tweets = tweets.order_by("created_at")#+
    data = []
    for tweet in tweets[:500]:
        # perturb locations slightly to avoid two tweets in "New York"
        # occluding one-anotheir on the map
        tweet.latitude += random.uniform(-.012, .012)
        tweet.longitude += random.uniform(-.012, .012)
        data.append({'text': tweet.tweet, 'latitude': tweet.latitude, 'longitude': tweet.longitude, 'image': tweet.profile_image_url, 'sentiment': tweet.sentiment})
        
    return "("+json.dumps(data)+");"
