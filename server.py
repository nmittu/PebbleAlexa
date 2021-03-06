from cloudant import Cloudant
from flask import Flask, render_template, redirect, request, jsonify
import atexit
import cf_deployment_tracker
import os
import json
import random
import string
from watson_developer_cloud import TextToSpeechV1, SpeechToTextV1
from requests import Request
import requests
import redis
import uuid
from pydub import AudioSegment
import tempfile
import re


#Alexa
Security_Profile_Description ="PebbleAlexa"
Security_Profile_ID  = "Security_Profile_ID"
Client_ID = "Client_ID"
Client_Secret = "Client_Secret"
Product_ID = "PebbleAlexa"

#Redis
redis_url = "127.0.0.1:6379"

text_to_speech = TextToSpeechV1(
    username='username',
    password='password')

speech_to_text = SpeechToTextV1(
	username='username',
	password='password')

# Emit Bluemix deployment event
cf_deployment_tracker.track()

app = Flask(__name__)

db_name = 'mydb'
client = None
db = None

# On Bluemix, get the port number from the environment variable PORT
# When running this app on the local machine, default the port to 8080
port = int(os.getenv('PORT', 443))


def gettoken(uid):
	red = redis.from_url(redis_url)
	token = red.get(uid+"-access_token")
	refresh = red.get(uid+"-refresh_token")
	if token:
		return token
	elif refresh:
		payload = {"client_id" : Client_ID, "client_secret" : Client_Secret, "refresh_token" : refresh, "grant_type" : "refresh_token", }
		url = "https://api.amazon.com/auth/o2/token"
		r = requests.post(url, data = payload)
		resp = json.loads(r.text)
		red.set(uid+"-access_token", resp['access_token'])
		red.expire(uid+"-access_token", 3600)
		return resp['access_token']
	else:
		return False


@app.route('/text/<strToConv>', methods=['POST'])
def home(strToConv):
	random_str = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(20))
	file_name = "/tmp/{}.wav".format(random_str)


	audio_file = text_to_speech.synthesize(strToConv, accept="audio/L16; rate=16000; channels=1", voice="en-US_AllisonVoice")

	uid = request.form.get("uid")
	token = gettoken(uid).decode('ascii')

	url = 'https://access-alexa-na.amazon.com/v1/avs/speechrecognizer/recognize'
	headers = {'Authorization' : 'Bearer %s' % token}
	d = {
		"messageHeader": {
			"deviceContext": [
				{
					"name": "playbackState",
					"namespace": "AudioPlayer",
					"payload": {
						"streamId": "",
						"offsetInMilliseconds": "0",
						"playerActivity": "IDLE"
					}
				}
			]
		},
		"messageBody": {
			"profile": "alexa-close-talk",
			"locale": "en-us",
			"format": "audio/L16; rate=16000; channels=1"
		}
	}
	files = [
		('file', ('request', json.dumps(d), 'application/json; charset=UTF-8')),
		('file', ('audio', audio_file, 'audio/L16; rate=16000; channels=1'))
	]
	r = requests.post(url, headers=headers, files=files)

	for v in r.headers['content-type'].split(";"):
		if re.match('.*boundary.*', v):
			boundary =  v.split("=")[1]

	data = r.content.split(bytes(boundary, encoding='utf-8'))
	for d in data:
		if (len(d) >= 1024):
			audio = d.split(b'\r\n\r\n')[1].rstrip(b'--')

	random_str = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(20))
	file_name = "/tmp/{}.wav".format(random_str)

	with open(file_name, 'wb') as audio_file:
		audio_file.write(audio)

	_input = AudioSegment.from_mp3(file_name)
	tf = tempfile.NamedTemporaryFile(suffix=".wav")
	output = _input.set_channels(1).set_frame_rate(16000)
	f = output.export(tf.name, format="wav")

	results = (speech_to_text.recognize(tf, content_type="audio/L16; rate=16000; channels=1", timestamps=False, word_confidence=False, continuous=True))["results"]
	tf.close()

	temp = ""
	for result in results:
		temp += result["alternatives"][0]["transcript"].capitalize()[:-1] + ". "

	#temp = json.dumps(speech_to_text.recognize(tf, content_type="audio/L16; rate=16000; channels=1", timestamps=False, word_confidence=False, continuous=True))#["results"][0]["alternatives"][0]["transcript"]
	return temp



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


@app.route('/code')
def code():
	code=request.args.get("code")
	path = path = request.url_root
	callback = path+"code"
	payload = {"client_id" : Client_ID, "client_secret" : Client_Secret, "code" : code, "grant_type" : "authorization_code", "redirect_uri" : callback }
	url = "https://api.amazon.com/auth/o2/token"
	r = requests.post(url, data = payload)
	uid = str(uuid.uuid4())
	red = redis.from_url(redis_url)
	resp = json.loads(r.text)
	print(red.set(uid+"-access_token", resp['access_token']))
	red.expire(uid+"-access_token", 3600)
	red.set(uid+"-refresh_token", resp['refresh_token'])
	return redirect("pebblejs://close#" + uid)

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
    app.run(host='0.0.0.0', port=port, debug=True, ssl_context=('fullchain.pem', 'privkey.pem'))
