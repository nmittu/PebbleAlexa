from cloudant import Cloudant
from flask import Flask, render_template, redirect, request, jsonify
import atexit
import cf_deployment_tracker
import os
import json
import random
import string
from watson_developer_cloud import TextToSpeechV1
from requests import Request
import requests


#Alexa
Security_Profile_Description ="PebbleAlexa"
Security_Profile_ID  = "amzn1.application.f82a211a43d34cb28773d844a3805ef4"
Client_ID = "amzn1.application-oa2-client.cee1c60d120347518b0c7db9b2cbb09a"
Client_Secret = "7bc082f3ab3ad004cf85f5500529935ce8f8ac61ae7c14f3ee7d8f3e31a7c74c"
Product_ID = "PebbleAlexa"

#Redis
redis_url = "127.0.0.1:6379"


text_to_speech = TextToSpeechV1(
    username='56ab11cb-ed91-4f77-acdc-f39d5c4b9e47',
    password='FURRaBf5FPaN')

# Emit Bluemix deployment event
cf_deployment_tracker.track()

app = Flask(__name__)

db_name = 'mydb'
client = None
db = None

# On Bluemix, get the port number from the environment variable PORT
# When running this app on the local machine, default the port to 8080
port = int(os.getenv('PORT', 8080))

@app.route('/text/<strToConv>')
def home(strToConv):
    random_str = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(20))
    file_name = "/tmp/{}.wav".format(random_str)

    with open(file_name, 'wb') as audio_file:
        audio_file.write(text_to_speech.synthesize(strToConv, accept="audio/wav", voice="en-US_AllisonVoice"))

    return strToConv + " written to " + file_name



@app.route('/auth')
def auth():
	scope="alexa_all"
	sd = json.dumps({
	    "alexa:all": {
	        "productID": Product_ID,
	        "productInstanceAttributes": {
	            "deviceSerialNumber": "1"
	        }
	    }
	})
	url = "https://www.amazon.com/ap/oa"
	path = request.url_root
	callback = path + "code"
	payload = {"client_id" : Client_ID, "scope" : "alexa:all", "scope_data" : sd, "response_type" : "code", "redirect_uri" : callback }
	req = Request('GET', url, params=payload)
	p = req.prepare()
	return redirect(p.url)

# /* Endpoint to greet and add a new visitor to database.
# * Send a POST request to localhost:8080/api/visitors with body
# * {
# * 	"name": "Bob"
# * }
# */
@app.route('/api/visitors', methods=['GET'])
def get_visitor():
    if client:
        return jsonify(list(map(lambda doc: doc['name'], db)))
    else:
        print('No database')
        return jsonify([])

# /**
#  * Endpoint to get a JSON array of all the visitors in the database
#  * REST API example:
#  * <code>
#  * GET http://localhost:8080/api/visitors
#  * </code>
#  *
#  * Response:
#  * [ "Bob", "Jane" ]
#  * @return An array of all the visitor names
#  */
@app.route('/api/visitors', methods=['POST'])
def put_visitor():
    user = request.json['name']
    if client:
        data = {'name':request.json['name']}
        db.create_document(data)
        return 'Hello %s! I added you to the database.' % user
    else:
        print('No database')
        return 'Hello %s!' % user

@atexit.register
def shutdown():
    if client:
        client.disconnect()

if __name__ == '__main__':
    app.run(host='pebblealexa.com', port=port, debug=True, ssl_context=('local.crt', 'local.key'))
