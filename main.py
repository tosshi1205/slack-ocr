import json

import requests
from flask import jsonify
from google.cloud import datastore
from google.cloud import vision_v1 as vision

with open('config.json') as f:
    data = f.read()
config = json.loads(data)


def text_detection(request):
    request_body = request.get_json()

    request_type = request_body['type']
    print(request_body)
    if request_type == 'url_verification':
        return jsonify({'challenge': request_body['challenge']})
    elif request_type == 'event_callback':
        event = request_body['event']
        file_id = event['file_id']

        message_api = 'https://slack.com/api/chat.postMessage'
        file_info = 'https://slack.com/api/files.info'

        SLACK_TOKEN = config['SLACK_TOKEN']
        GCP_PROJECT_ID = config['GCP_PROJECT_ID']

        client = datastore.Client(GCP_PROJECT_ID)

        query = client.query(kind=config['DATASTORE_KIND'])
        query.add_filter('fileid', '=', file_id)
        entities = list(query.fetch())

        if not entities:
            incomplete_key = client.key(config['DATASTORE_KIND'])
            task = datastore.Entity(key=incomplete_key)
            task.update({
                'fileid': file_id
            })

            client.put(task)
        else:
            print('file: {} was already analyzed.'.format(file_id))
            return jsonify({'success': 'ok'})

        HEADERS = {'Content-Type': 'application/json',
                   'Authorization': 'Bearer {}'.format(SLACK_TOKEN)}

        response = requests.get(
            file_info, headers=HEADERS, params={'file': file_id})
        mimetype = response.json()['file']['mimetype']

        if mimetype.startswith('image'):
            download_url = response.json()['file']['url_private_download']
            channel = response.json()['file']['channels'][0]

            response = requests.get(
                download_url, headers=HEADERS)
            content = response.content

            client = vision.ImageAnnotatorClient()
            image = vision.types.Image(content=content)
            ocr = client.text_detection(image=image)
            response = requests.post(message_api, headers=HEADERS,
                                     json={'channel': channel,
                                           'text': ocr.full_text_annotation.text})
            print(response)

        return jsonify({'success': 'ok'})
