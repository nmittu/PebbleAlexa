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
Security_Profile_ID  = "amzn1.application.f82a211a43d34cb28773d844a3805ef4"
Client_ID = "amzn1.application-oa2-client.cee1c60d120347518b0c7db9b2cbb09a"
Client_Secret = "7bc082f3ab3ad004cf85f5500529935ce8f8ac61ae7c14f3ee7d8f3e31a7c74c"
Product_ID = "PebbleAlexa"

#Redis
redis_url = "127.0.0.1:6379"

text_to_speech = TextToSpeechV1(
    username='56ab11cb-ed91-4f77-acdc-f39d5c4b9e47',
    password='FURRaBf5FPaN')

speech_to_text = SpeechToTextV1(
	username='cf1e2311-a8e0-4792-9e58-a16dd9cdd6b9',
	password='zPYxyQMm5CFJ')

# Emit Bluemix deployment event
cf_deployment_tracker.track()

app = Flask(__name__)

db_name = 'mydb'
client = None
db = None

# On Bluemix, get the port number from the environment variable PORT
# When running this app on the local machine, default the port to 8080
port = int(os.getenv('PORT', 443))

@app.route('/text/<strToConv>', methods=['POST'])
def home(strToConv):
	random_str = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(20))
	file_name = "/tmp/{}.wav".format(random_str)

	with open(file_name, 'wb') as audio_file:
		audio_file.write(text_to_speech.synthesize(strToConv, accept="audio/wav", voice="en-US_AllisonVoice"))

	_input = AudioSegment.from_wav(file_name)
	tf = tempfile.NamedTemporaryFile(suffix=".wav")
	output = _input.set_channels(1).set_frame_rate(16000)
	f = output.export(tf.name, format="wav")

	red = redis.from_url(redis_url)

	uid = request.form.get("uid")
	token = red.get(uid+"-access_token").decode('ascii')

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
		('file', ('audio', tf, 'audio/L16; rate=16000; channels=1'))
	]
	r = requests.post(url, headers=headers, files=files)
	tf.close()

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

	with open(file_name, 'rb') as audio_file:
		return json.dumps(speech_to_text.recognize(audio_file, content_type="audio/wav", timestamps=True, word_confidence=True, indent=2))



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
	#red.expire(uid+"-access_token", 3600)
	red.set(uid+"-refresh_token", resp['refresh_token'])
	return uid

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
    app.run(host='0.0.0.0', port=port, debug=True, ssl_context=('local.crt', 'local.key'))
