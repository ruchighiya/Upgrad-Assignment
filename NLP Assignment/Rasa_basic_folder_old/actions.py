from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from rasa_sdk import Action
from rasa_sdk.events import SlotSet
import zomatopy
import json
from email.message import EmailMessage
import requests
import smtplib
from concurrent.futures import ThreadPoolExecutor
d_email_rest = []
class ActionSearchRestaurants(Action):
    def name(self):
        return 'action_search_restaurants'
        
    def run(self, dispatcher, tracker, domain):
        config={ "user_key": "5acfcec645af08a0f4051a29c58c255b"}
        #config = {'user_key':"455c41499144739a6f131347a8130495"}
        zomato = zomatopy.initialize_app(config)
        loc = tracker.get_slot('location')
        cuisine =tracker.get_slot('cuisine')
        min_cost=tracker.get_slot('budgetmin')
        max_cost=tracker.get_slot('budgetmax')
        location_detail=zomato.get_location(loc, 1)
        d1 = json.loads(location_detail)
        lat=d1["location_suggestions"][0]["latitude"]
        lon=d1["location_suggestions"][0]["longitude"]
        results=zomato.restaurant_search("", lat, lon)
        d = json.loads(results)
        response=""
        if d['results_found'] == 0:
            response= "no results"
            dispatcher.utter_message("Sorry, no restaurant found in this location:("+ "\n")
        else:
            d_rest = self.get_restaurants(lat, lon, min_cost, max_cost, cuisine)
            
            # Filter the results based on budget
            d_budget = [d_rest_single for d_rest_single in d_rest if ((d_rest_single['restaurant']['average_cost_for_two'] > cost_min) & (d_rest_single['restaurant']['average_cost_for_two'] < cost_max))]

            # Sort the results according to the restaurant's rating
            d_budget_rating_sorted = sorted(d_budget, key=lambda k: k['restaurant']['user_rating']['aggregate_rating'], reverse=True)

            # Build the response
            response = ""
            restaurant_exist = False
            if len(d_budget_rating_sorted) == 0:
                dispatcher.utter_message("Sorry, no results found :("+ "\n")
            else:
                # Pick the top 5 restaurant
                d_budget_rating_top5 = d_budget_rating_sorted[:5]
                global d_email_rest
                d_email_rest = d_budget_rating_sorted[:10]
                if(d_email_rest and len(d_email_rest) > 0):
                    restaurant_exist = True
                for restaurant in d_budget_rating_top5:
                    response = response + restaurant['restaurant']['name'] + " in " + restaurant['restaurant']['location']['address'] + \
                            " has been rated " + restaurant['restaurant']['user_rating']['aggregate_rating'] + "\n" + "\n"
                dispatcher.utter_message("Here are our picks!"+ "\n" + response)
        return [SlotSet('location', loc), SlotSet('restaurant_exist', restaurant_exist)]
    
    def get_location_suggestions(self, loc, zomato):
        # Get location details including latitude and longitude
        location_detail = zomato.get_location(loc, 1)
        d1 = json.loads(location_detail)
        lat = 0
        lon = 0
        results = len(d1["location_suggestions"])
        if (results > 0):
            lat = d1["location_suggestions"][0]["latitude"]
            lon = d1["location_suggestions"][0]["longitude"]
        return results, lat, lon
            
    def get_restaurants(self, lat, lon, budgetmin, budgetmax , cuisine):
        cuisines_dict = {'american': 1, 'chinese': 25, 'italian': 55,
                         'mexican': 73, 'north indian': 50, 'south indian': 85}
        d_rest = []
        executor = ThreadPoolExecutor(max_workers=5)
        for res_key in range(0, 101, 20):
            executor.submit(retrieve_restaurant, lat, lon, cuisines_dict, cuisine, res_key, d_rest)
        executor.shutdown()
        return d_rest
        
    
class VerifyLocation(Action):

    tier_1 = []
    tier_2 = []
    
    def __init__(self):
        self.tier_1 = ['ahmedabad', 'bangaluru', 'chennai', 'delhi', 'hyderabad', 'kolkata', 'mumbai', 'pune']
        self.tier_2 = ['Agra','Ajmer','Aligarh','Amravati','Amritsar','Asansol','Aurangabad','Bareilly','Belgaum',
                        'Bhavnagar','Bhiwandi','Bhopal','Bhubaneswar','Bikaner','Bilaspur','Bokaro Steel City','Chandigarh',
                        'Coimbatore','Cuttack','Dehradun','Dhanbad','Bhilai','Durgapur','Dindigul','Erode','Faridabad','Firozabad',
                        'Ghaziabad','Gorakhpur','Gulbarga','Guntur','Gwalior','Gurgaon','Guwahati','Hamirpur','Hubli–Dharwad','Indore',
                        'Jabalpur','Jaipur','Jalandhar','Jammu','Jamnagar','Jamshedpur','Jhansi','Jodhpur','Kakinada','Kannur','Kanpur',
                        'Karnal','Kochi','Kolhapur','Kollam','Kozhikode','Kurnool','Ludhiana','Lucknow','Madurai','Malappuram','Mathura',
                        'Mangalore','Meerut','Moradabad','Mysore','Nagpur','Nanded','Nashik','Nellore','Noida','Patna','Pondicherry','Purulia',
                        'Prayagraj','Raipur','Rajkot','Rajahmundry','Ranchi','Rourkela','Salem','Sangli','Shimla','Siliguri','Solapur','Srinagar',
                        'Surat','Thanjavur','Thiruvananthapuram','Thrissur','Tiruchirappalli','Tirunelveli','Ujjain','Bijapur','Vadodara','Varanasi',
                        'Vasai-Virar City','Vijayawada','Visakhapatnam','Vellore','Warangal']
    def name(self):
        return "check_location"
        
    def run(self, dispatcher, tracker, domain):
        loc = tracker.get_slot('location')
        if not (self.check_location(loc)):
            dispatcher.utter_message("We do not operate in " + loc + " this location yet. Please try in some other city.")
            return [SlotSet('location', None), SlotSet("location_ok", False)]
        else:
            return [SlotSet('location', loc), SlotSet("location_ok", True)]
            
    def check_location(self, loc):
        return loc.lower() in self.tier_1 or loc.lower() in self.tier_2

class ActionSendEmail(Action):
    def name(self):
        return 'action_send_email'
        
    def run(self, dispatcher, tracker, domain):
        # Get user's email id
        to_email = tracker.get_slot('emailid')
        # Get location and cuisines
        loc = tracker.get_slot('location')
        cuisine = tracker.get_slot('cuisine')
        global d_email_rest
        email_rest_count = len(d_email_rest)
        # Construct the email 'subject' and the contents.
        d_email_subj = "Top " + str(email_rest_count) + " " + cuisine.capitalize() + " restaurants in " + str(loc).capitalize()
        d_email_msg = "Hi there! Here is the of top rated restaurants" + d_email_subj + "." + "\n" + "\n" +"\n"
        for restaurant in d_email_rest:
            d_email_msg = d_email_msg + restaurant['restaurant']['name']+ " in "+ restaurant['restaurant']['location']['address']+" has been rated " + restaurant['restaurant']['user_rating']['aggregate_rating'] + "\n" +"\n"
            
        # Open SMTP connection to our email id.
        session = smtplib.SMTP("smtp.gmail.com", 587)
        session.starttls()#enable security
        session.login("upgrad.chatbot@gmail.com", "mlaiupgrad")
        
        # Create the msg object
        msg = EmailMessage()
        
        # Fill in the message properties
        msg['Subject'] = d_email_subj
        msg['From'] = "upgrad.chatbot@gmail.com"
        
        # Fill in the message content
        msg.set_content(d_email_msg)
        msg['To'] = to_email
        s.send_message(msg)
        s.quit()
        dispatcher.utter_message(" EMAIL SENT! Hope you enjoy your meal ")
        return []
        
class VerifyPrice(Action):
    
    def name(self):
        return "verify_price"
        
    def run(self, dispatcher, tracker, domain):
        budgetmin = None
        budgetmax = None
        error_msg = "Please enter the valid price range."
        try:
            budgetmin = int(tracker.get_slot('budgetmin'))
            budgetmax = int(tracker.get_slot('budgetmax'))
        except ValueError:
            dispatcher.utter_message(error_msg)
            return [SlotSet('budgetmin', None), SlotSet('budgetmax', None), SlotSet('budget_ok', False)]
        min_dict = [0, 300, 700]
        max_dict = [300, 700]
        if budgetmin in min_dict and (budgetmax in max_dict or budgetmax > 700):
            return [SlotSet('budgetmin', budgetmin), SlotSet('budgetmax', budgetmax), SlotSet('budget_ok', True)]
        else:
            dispatcher.utter_message(error_msg)
            return [SlotSet('budgetmin', 0), SlotSet('budgetmax', 10000), SlotSet('budget_ok', False)]

    
class VerifyCuisine(Action):
    
    def name(self):
        return "check_cusine"
        
    def run(self, dispatcher, tracker, domain):
        cuisines = ['chinese','mexican','italian','american','south indian','north indian']
        error_msg = "Sorry!! The cuisine is not supported. Please re-enter."
        cuisine = tracker.get_slot('cuisine')
        try:
            cuisine = cuisine.lower()
        except (RuntimeError, TypeError, NameError, AttributeError):
            dispatcher.utter_message(error_msg)
            return [SlotSet('cuisine', None), SlotSet('cuisine_ok', False)]
        if cuisine in cuisines:
            return [SlotSet('cuisine', cuisine), SlotSet('cuisine_ok', True)]
        else:
            dispatcher.utter_message(error_msg)
            return [SlotSet('cuisine', None), SlotSet('cuisine_ok', False)]
            
    def retrieve_restaurant(lat, lon, cuisines_dict, cuisine, res_key, d_rest):
        base_url = "https://developers.zomato.com/api/v2.1/"
        headers = {'Accept': 'application/json','user-key': '5acfcec645af08a0f4051a29c58c255b'}
        try:
            results = (requests.get(base_url + "search?" + "&lat=" + str(lat) + "&lon=" + str(lon) + "&cuisines=" + str(
                cuisines_dict.get(cuisine)) + "&start=" + str(res_key)+"&count=20", headers=headers).content).decode("utf-8")
        except:
            return
        d = json.loads(results)
        d_rest.extend(d['restaurants'])
