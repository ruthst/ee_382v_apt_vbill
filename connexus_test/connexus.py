import os
import urllib
from datetime import datetime, timedelta
import time

from google.appengine.api import users
from google.appengine.api import mail, images
from google.appengine.ext import ndb
from google.appengine.ext import blobstore, deferred
from google.appengine.ext.webapp import blobstore_handlers

import jinja2
import webapp2
import re
import json


# img_info = {} #for now this is empty at startup, when app is deployed need to figure out how to store img_info to datastore and retrieve for each user

def cleanup(blob_keys):
    blobstore.delete(blob_keys)


JINJA_ENVIRONMENT = jinja2.Environment(
	loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
  extensions=['jinja2.ext.autoescape'],
  autoescape=True)


popStreams = []

class ImageStream(ndb.Model):
	# models image stream with stream_name, owner, subscriber?
	# need json dumb/property for all other info?
	# stream1.put() creates in datastore, stream1.get()?
	# can use @classmethod to create a default query? get all?
	stream_name = ndb.StringProperty()
	owner = ndb.StringProperty()
	subscribers = ndb.StringProperty(repeated=True)
	tags = ndb.StringProperty(repeated=True)
	info = ndb.JsonProperty()
	timestamps = ndb.StringProperty(repeated=True)

class MainPage(webapp2.RequestHandler):
	#main page = login, should check for login then dump to manage page?
  def get(self):
		user = users.get_current_user()
		if user:
			greeting = ('Welcome, %s!' % (user.nickname()))
			url = users.create_logout_url('/')
			url_linktext = 'Logout'
			template_values = {
 			'greeting': greeting,
			'url': url,
 			'url_linktext': url_linktext,
 			}
			template = JINJA_ENVIRONMENT.get_template('manage.html')
			self.response.write(template.render(template_values))
		else:
			greeting = 'Sign in or register:'
			url = users.create_login_url(self.request.uri)
			url_linktext = 'Login'
			template_values = {
 				'greeting': greeting,
				'url': url,
 				'url_linktext': url_linktext,
 			}
			template = JINJA_ENVIRONMENT.get_template('index.html')
 			self.response.write(template.render(template_values))


class Manage(webapp2.RequestHandler):
	def get(self):
		user = users.get_current_user()
		if user:
			greeting = ('Welcome, %s!' % (user.nickname()))
			url = users.create_logout_url('/')
			url_linktext = 'Logout'
			template_values = {
			'greeting': greeting,
      'url': url,
      'url_linktext': url_linktext,
  		}

			all_streams_user = ImageStream.query(ImageStream.owner == user.nickname()).fetch()
			img_info = {}
			for x in xrange(len(all_streams_user)):
				img_info[all_streams_user[x].stream_name] = all_streams_user[x].info
			if len(img_info) > 0:
				template_values['streams'] = img_info
			else:
				template_values['command'] = 'Nothing here yet, either create or subscribe to streams to manage'
		else:
			url = users.create_login_url(self.request.uri)
			url_linktext = 'Login'
			template_values = {
      'url': url,
      'url_linktext': url_linktext,
  		}

		template = JINJA_ENVIRONMENT.get_template('manage.html')
		self.response.write(template.render(template_values))
		
	def post(self):
		print 'entered post'
		to_delete = self.request.get_all('delete')
		print to_delete
		del_stream = ImageStream.query(ImageStream.stream_name == to_delete[0]).fetch()
		print del_stream
		del_key = del_stream[0].key
		print del_key
		del_key.delete()
		#del_stream[0].delete()
		time.sleep(0.1)
		self.redirect('/manage')


class Create(webapp2.RequestHandler):
	def get(self):
		user = users.get_current_user()
		if user:
			url = users.create_logout_url('/')
			url_linktext = 'Logout'
		else:
			url = users.create_login_url(self.request.uri)
			url_linktext = 'Login'

		# the create page serves as the MainHandler for the create stream UploadHandler, ServeHandler
		upload_url = blobstore.create_upload_url('/upload')

		template_values = {
      'url': url,
      'url_linktext': url_linktext,
			'upload_url': upload_url,
  	}
		template = JINJA_ENVIRONMENT.get_template('create_stream.html')
		self.response.write(template.render(template_values))

#class CreateStreamHandler(webapp2.RequestHandler):
	#def post(self):
 
# Need to add tuple of date/time to image url, ndb.DateTimeProperty()? 
# Or, use python datetime.datetime module

class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
  def post(self):
		#print upload_type
		print 'entered upload'
		if self.request.get('stream_name'):
			print 'entered create'
			user = users.get_current_user()
			print users.get_current_user()
			print type(user.nickname())
			
			upload_files = self.get_uploads('cover_url')  # 'file' is file upload field in the form
			stream_name = self.request.get('stream_name')
			blob_info = upload_files[0]
			print 'stream name = %s' % stream_name
			img_info = {}
			img_info[stream_name] = {}
			upload_time = datetime.now()
			img_info[stream_name]['cover'] = (images.get_serving_url(blob_info.key()), str(upload_time.date()))
			img_info[stream_name]['stream_urls'] = [(images.get_serving_url(blob_info.key()), str(upload_time.date()))]
			img_info[stream_name]['stream_len'] = 1
			img_info[stream_name]['subscribers'] = [self.request.get('subscribers')] #need regex to parse multiple subscribers??????
			img_info[stream_name]['tags'] = [self.request.get('tags')] # should this be a list or just string? need regex?
			img_info[stream_name]['views'] = 1
			img_info[stream_name]['timestamps'] = [ str(datetime.now()) ]
			invite_message = self.request.get('invite_message') 
			data_stream = ImageStream(stream_name=self.request.get('stream_name'), owner=user.nickname(), subscribers = [self.request.get('subscribers')], tags=[self.request.get('tags')], info = img_info)
			data_stream_key = data_stream.put()
			#print img_info
			#print images.get_serving_url(blob_info.key())
			#print data_stream_key
			time.sleep(0.1)
			self.redirect('/manage',permanent=True)

		elif self.request.get('file_name'):
			print 'entered add image'
			stream_name = self.request.get('this_stream')
			print stream_name			
			upload_files = self.get_uploads('new_image')  # 'file' is file upload field in the form
			blob_info = upload_files[0]
			upload_time = datetime.now()
			single_stream = ImageStream.query(ImageStream.stream_name == stream_name).fetch()
			single_stream[0].info[stream_name]['stream_urls'].append((images.get_serving_url(blob_info.key()), str(upload_time.date())))
			single_stream[0].info[stream_name]['stream_len'] += 1
			single_stream[0].info[stream_name]['comments'] = [self.request.get('comments')] # needs to be tuple to find associated image?
			single_stream[0].put()
			print single_stream
			print images.get_serving_url(blob_info.key())
			time.sleep(0.1)
			self.redirect('/viewsingle'+'/'+stream_name)

class ServeHandler(blobstore_handlers.BlobstoreDownloadHandler):
  def get(self, resource):
		print 'entered serve'
		resource = str(urllib.unquote(resource))
		blob_info = blobstore.BlobInfo.get(resource)
		print images.get_serving_url(blob_info.key())
		img_url = images.get_serving_url(blob_info.key())
		self.send_blob(blob_info)
		#self.redirect('/manage')

class View(webapp2.RequestHandler):
	#clicking on view tab should take you to view all streams page
	def get(self):
		user = users.get_current_user()
		if user:
			url = users.create_logout_url('/')
			url_linktext = 'Logout'
			template_values = {
		    'url': url,
		    'url_linktext': url_linktext,
			}
			all_streams = ImageStream.query().fetch()
			img_info = {}
			for x in xrange(len(all_streams)):
				img_info[all_streams[x].stream_name] = all_streams[x].info
			if len(img_info) > 0:
				template_values['streams'] = img_info
			else:
				template_values['command'] = 'Nothing here yet, either create or subscribe to streams to view all'
		else:
			url = users.create_login_url(self.request.uri)
			url_linktext = 'Login'
			template_values = {
		    'url': url,
		    'url_linktext': url_linktext,
			}
		template = JINJA_ENVIRONMENT.get_template('view_astreams.html')
		self.response.write(template.render(template_values))

class ViewSingle(webapp2.RequestHandler):
	#clicking on view tab should take you to view all streams page
	def get(self, stream_name):
		print 'entered single stream handler' #debugging, clean up later
		print stream_name

		# img_info[stream_name]['views'] += 1
		# the create page serves as the MainHandler for the create stream UploadHandler, ServeHandler
		upload_url = blobstore.create_upload_url('/upload')
		user = users.get_current_user()
		if user:
			url = users.create_logout_url('/')
			url_linktext = 'Logout'
			template_values = {
		    'url': url,
		    'url_linktext': url_linktext,
				'upload_url': upload_url,
			}

			single_stream = ImageStream.query(ImageStream.stream_name == stream_name).fetch()
			single_stream[0].info[stream_name]['views'] += 1
			single_stream[0].info[stream_name]['timestamps'].append( str(datetime.now()) )
			single_stream[0].put()
			print single_stream

			img_info = {}
			for x in xrange(len(single_stream)):
				img_info[single_stream[x].stream_name] = single_stream[x].info

			#if self.request.get('more_check') == None:
			if not self.request.get('more_check'):
				img_info[stream_name][stream_name]['stream_urls'] = img_info[stream_name][stream_name]['stream_urls'][0:3]
				template_values['more_check'] = 0
			else:
				template_values['more_check'] = 1
			if len(img_info) > 0:
				template_values['streams'] = img_info
				template_values['this_stream'] = stream_name
		else:
			url = users.create_login_url(self.request.uri)
			url_linktext = 'Login'
			template_values = {
		    'url': url,
		    'url_linktext': url_linktext,
			}
		template = JINJA_ENVIRONMENT.get_template('view_sstream.html')
		self.response.write(template.render(template_values))

class Search(webapp2.RequestHandler):
	def get(self):
		user = users.get_current_user()
		if user:
			url = users.create_logout_url('/')
			url_linktext = 'Logout'
		else:
			url = users.create_login_url(self.request.uri)
			url_linktext = 'Login'
		template_values = {
      'url': url,
      'url_linktext': url_linktext,
  	}
		template = JINJA_ENVIRONMENT.get_template('search.html')
		self.response.write(template.render(template_values))

class SearchStreams(webapp2.RequestHandler):
	def post(self):
		search_data = self.request.get('cxus_search')
		print search_data

		user = users.get_current_user()
		if user:
			url = users.create_logout_url('/')
			url_linktext = 'Logout'
		else:
			url = users.create_login_url(self.request.uri)
			url_linktext = 'Login'
		template_values = {
      'url': url,
      'url_linktext': url_linktext,
  	}

  		#get search results from stream name
		search_results = ImageStream.query(ImageStream.stream_name == search_data).fetch()

		this_name = {}
		print search_results
		for x in xrange(len(search_results)):
				this_name[search_results[x].stream_name] = search_results[x].info

		# add all_streams_tags for streams with those tags
		all_streams_tags = ImageStream.query(ImageStream.tags > '').fetch()
		print all_streams_tags
		this_tag = {}
		for x in xrange(len(all_streams_tags)):
				if any(search_data in y for y in all_streams_tags[x].tags):
					this_tag[all_streams_tags[x].stream_name] = all_streams_tags[x].info
	
		#combine name reslts with tag results
		img_info = dict(this_name.items() + this_tag.items())

		#reduce to 5 results if more than that
		while (len(img_info)) > 5:
			img_info.popitem()

		if (len(img_info)) > 0:
			template_values['streams'] = img_info  #TODO CHANGE TO ONLY SHOW 5
		else:
			template_values['command'] = 'No matching streams found'

		template = JINJA_ENVIRONMENT.get_template('search_results.html')
		self.response.write(template.render(template_values))

class Trending(webapp2.RequestHandler):
	def get(self):
		user = users.get_current_user()
		if user:
			url = users.create_logout_url('/')
			url_linktext = 'Logout'
		else:
			url = users.create_login_url(self.request.uri)
			url_linktext = 'Login'
		template_values = {
      'url': url,
      'url_linktext': url_linktext,
  	}
		template = JINJA_ENVIRONMENT.get_template('trending.html')
		self.response.write(template.render(template_values))

		trending_streams = getTrends()
		if len(trending_streams) > 0:
			template_values['streams'] = trending_streams
		else:
			template_values['command'] = 'No trending streams found'

class TrendingShort(webapp2.RequestHandler):
	def post(self):
		print "Been 5 minutes"
		freshenTrends()
		if buttonPosition == short_update:
			sendTrends() 

class TrendingHourly(webapp2.RequestHandler):
	def post(self):
		print "Been an hour"
		#CHECK LAST UPDATED TREND TIME BUTTON
		if buttonPosition == hourly_update:
			sendTrends() 


class TrendingDaily(webapp2.RequestHandler):
	def post(self):
		print "Been a day"
		#CHECK LAST UPDATED TREND TIME BUTTON
		if buttonPosition == daily_update:
			sendTrends() 


#Called every 5 minutes to clean out old timestamps 
def freshenTrends():
	print "in freeshenTrends"
	'''
	Load up all the stream info
	'''
	all_streams = ImageStream.query().fetch()
	img_info = {}
	for x in xrange(len(all_streams)):
		img_info[all_streams[x].stream_name] = all_streams[x].info


	'''
	Clear out times older than hour
	'''
	current_time = str(datetime.now())
	for stream in img_info:
		index = 0
		converted_time = time.strptime(img_info.timestamps[index], "%Y-%m-%d %H:%M:%S.%f" )
		while (current_time - converted_time) > timedelta(hours = 1):
			img_info[stream].timestamps.remove(converted_time)
			index += 1
			converted_time = time.strptime( img_info[stream].timestamps[index], "%Y-%m-%d %H:%M:%S.%f" )

	'''
	Get most viewed streams for past hour
	'''
	for stream_name in img_info:
		popStreams[stream] = (len(img_info[stream_name]['timestamps']), streamName)
	popStreams.sort()

	return

#returns the top 3 trends
def getTrends():
	print "in getTrends"
	if len(popStreams) < 3:
		freshenTrends() 
	return popStreams[0:3]


def sendTrends():
	trending_streams = getTrends()

	#TODO FIX SENDING EMAIL
	message = mail.EmailMessage(sender=user.email(), subject="Trending Update")
	message.to = user.email
	message.body = "CONNEXUS.US\n",
	message.body += 	"Daily Trending Report\n",
	message.body += "------------------------------------------\n",
	message.body += "1. ", trending_streams[0], "\n",
	message.body += "2. ", trending_streams[1], "\n",
	message.body += "3. ", trending_streams[2], "\n"
		#"Update Trending Prefrerences (Link)"
	message.send()
	self.redirect('/')

class Social(webapp2.RequestHandler):
	def get(self):
		user = users.get_current_user()
		if user:
			url = users.create_logout_url('/')
			url_linktext = 'Logout'
		else:
			url = users.create_login_url(self.request.uri)
			url_linktext = 'Login'
		template_values = {
      'url': url,
      'url_linktext': url_linktext,
  	}
		template = JINJA_ENVIRONMENT.get_template('social.html')
		self.response.write(template.render(template_values))



class InviteFriendHandler(webapp2.RequestHandler):
	def post(self):
		user = users.get_current_user()
		if user is None:
			login_url = users.create_login_url(self.request.path)
			self.redirect(login_url)
			return
		to_addr = self.request.get("invite_email")
		if not mail.is_email_valid(to_addr):
  		# Return an error message...
			pass

		message = mail.EmailMessage(sender=user.email(), subject="test invite")
		message.to = to_addr
		message.body = "this is a test message"
		message.send()
		self.redirect('/')

class DeleteStream(webapp2.RequestHandler):
	def get(self):
		print 'entered delete'
		user = users.get_current_user()
		if user is None:
			login_url = users.create_login_url(self.request.path)
			self.redirect(login_url)
			return
		
		to_delete = self.request.get_all('delete')
		print to_delete
		#stream_del = ImageStream.query(ImageStream.stream_name == stream_name).fetch()
		#stream_del[0].delete()
		
		time.sleep(0.1)
		self.redirect('/manage')


class NotFoundPageHandler(webapp2.RequestHandler):
	def get(self, resource):
		self.error(404)
		user = users.get_current_user()
		if user:
			url = users.create_logout_url('/')
			url_linktext = 'Logout'
		else:
			url = users.create_login_url(self.request.uri)
			url_linktext = 'Login'
		template_values = {
      'url': url,
      'url_linktext': url_linktext,
  	}
		# switch(resource) {
		#	case 'snamediff':
		#		template_values['error_msg'] = 'You already have a stream with that name, please pick another name for your new stream'
		#		break;
		#}
		# error_msg = resource
		template = JINJA_ENVIRONMENT.get_template('error.html')
		self.response.write(template.render(template_values))	


application = webapp2.WSGIApplication([
  ('/', MainPage),
  ('/invite', InviteFriendHandler),
	('/manage', Manage),
	('/create', Create),
	('/viewall', View),
	('/viewsingle/([^/]+)?', ViewSingle),
	('/search', Search),
	('/searchstreams', SearchStreams),
	('/trending', Trending),
	('/trendingShort', TrendingShort),
	('/TrendingHourly', TrendingHourly),
	('/trendingDaily', TrendingDaily),
	('/social', Social),
	('/upload', UploadHandler),
	('/delete', DeleteStream),
	('/serve/([^/]+)?', ServeHandler),
	('/.*', NotFoundPageHandler),
], debug=True)
