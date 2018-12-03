import hashlib
import hmac
import time
from threading import Thread

from flask import Flask, jsonify, request, abort
from slackclient import SlackClient
import json
import os
import sys
import pprint
import requests

pp = pprint.PrettyPrinter(indent=4)
app = Flask(__name__)

# config
config_filename = "config.json"

if not os.path.isfile(config_filename):
    print("Config file does not exist. Please create a config file named: `config.json`. See config.json.template")
    sys.exit(1)

with open("config.json") as f:
    config_vals = json.load(f)
    slack_oauth_token = config_vals["SLACK_OAUTH_TOKEN"]
    slack_signing_secret = config_vals["SLACK_SIGNING_SECRET"]

slack = SlackClient(slack_oauth_token)


# api endpoints
@app.route('/')
def hello_world():
    return "Hello World"


@app.route('/post/<string:post_id>')
def show_post(post_id):
    return 'Post %s' % post_id


@app.route('/slack/matrix', methods=['POST'])
def handle_matrix():
    try:
        # verify the slack signature
        raw_body = request.get_data()
        slack_request_timestamp = request.headers['X-Slack-Request-Timestamp']
        slack_signature = request.headers['X-Slack-Signature']
        if not verify_signature(slack_signing_secret, slack_request_timestamp, slack_signature, raw_body):
            abort(400)

        # message verified, do matrix
        content = request.form
        thread = Thread(target=do_matrix, args=(content,))
        thread.start()
        return jsonify({'response_type': "in_channel"})
    except KeyError:
        abort(400, {'message': 'slack verification headers missing'})


def do_matrix(content):
    channel_id = content["channel_id"]
    response_url = content["response_url"]
    response = try_api_call("conversations.members", channel=channel_id)
    channel_members = response["members"]
    user_names = list(map(get_name_from_user_id, channel_members))
    rotated_user_names = user_names[1:] + user_names[:1]
    pairs = [(user_names[x], rotated_user_names[x]) for x in range(len(user_names))]
    payload = {'response_type': 'in_channel',
               'text': pprint_pairs(pairs)}
    requests.post(response_url, json=payload)
    return payload


def pprint_pairs(pairs):
    str_list = ['```']
    for pair in pairs:
        str_list.append("{:30} | {:30}".format(pair[0], pair[1]))
    str_list.append("```")
    return "\n".join(str_list)


def try_api_call(api_call_method, **kwargs):
    response = slack.api_call(api_call_method, **kwargs)
    if "error" in response:
        pp.pprint(response)
        raise Exception("Error occurred during api call")
    return response


def get_name_from_user_id(user_id):
    response = try_api_call("users.info", user=user_id)
    return response["user"]["real_name"]


# from https://github.com/slackapi/python-slack-events-api/blob/master/slackeventsapi/server.py
def verify_signature(signing_secret, timestamp, signature, raw_body):
    if abs(int(time.time()) - int(timestamp)) > 60 * 5:
        # The request timestamp is more than five minutes from local time.
        # It could be a replay attack, so let's ignore it.
        return False

    # Verify the request signature of the request sent from Slack
    # Generate a new hash using the app's signing secret and request data

    # Compare the generated hash and incoming request signature
    # Python 2.7.6 doesn't support compare_digest
    # It's recommended to use Python 2.7.7+
    # noqa See https://docs.python.org/2/whatsnew/2.7.html#pep-466-network-security-enhancements-for-python-2-7
    if hasattr(hmac, "compare_digest"):
        req = str.encode('v0:' + str(timestamp) + ':') + raw_body
        request_hash = 'v0=' + hmac.new(
            str.encode(signing_secret),
            req, hashlib.sha256
        ).hexdigest()

        # Compare byte strings for Python 2
        if sys.version_info[0] == 2:
            return hmac.compare_digest(bytes(request_hash), bytes(signature))
        else:
            return hmac.compare_digest(request_hash, signature)
    else:
        # So, we'll compare the signatures explicitly
        req = str.encode('v0:' + str(timestamp) + ':') + request.data
        request_hash = 'v0=' + hmac.new(
            str.encode(signing_secret),
            req, hashlib.sha256
        ).hexdigest()

        if len(request_hash) != len(signature):
            return False
        result = 0
        if isinstance(request_hash, bytes) and isinstance(signature, bytes):
            for x, y in zip(request_hash, signature):
                result |= x ^ y
        else:
            for x, y in zip(request_hash, signature):
                result |= ord(x) ^ ord(y)
        return result == 0


if __name__ == "__main__":
    app.run(host="localhost")
