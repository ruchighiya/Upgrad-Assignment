from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from rasa_sdk import Action
from rasa_sdk.events import SlotSet
import zomatopy
import json

class ActionSearchRestaurants(Action):
	def name(self):
		return 'action_search_restaurants'
		
	def run(self, dispatcher, tracker, domain):
		config={ "user_key":"f4924dc9ad672ee8c4f8c84743301af5"}
		#config = {'user_key':"455c41499144739a6f131347a8130495"}
		zomato = zomatopy.initialize_app(config)
		loc = tracker.get_slot('location')
		cuisine = tracker.get_slot('cuisine')
		location_detail=zomato.get_location(loc, 1)
		d1 = json.loads(location_detail)
		lat=d1["location_suggestions"][0]["latitude"]
		lon=d1["location_suggestions"][0]["longitude"]
		cuisines_dict={'Chinese':5,'Mexican':25,'Italian':30,'American':55,'north indian':50,'south indian':85}
		results=zomato.restaurant_search("", lat, lon, str(cuisines_dict.get(cuisine)), 5)
		d = json.loads(results)
		response=""
		if d['results_found'] == 0:
			response= "no results"
		else:
			for restaurant in d['restaurants']:
				response=response+ "Found "+ restaurant['restaurant']['name']+ " in "+ restaurant['restaurant']['location']['address']+"\n"
		
		dispatcher.utter_message("---------"+response)

		return [SlotSet('location',loc)]

class CheckLocation(Action):
	def name(self):
		return 'check_location'
		
	def run(self, dispatcher, tracker, domain):

		loc = tracker.get_slot('location')
		if validate_location(loc):
			SlotSet('check_op',True)
		else:
			SlotSet('check_op',False)
		return True
