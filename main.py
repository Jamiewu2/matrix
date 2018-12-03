from threading import Thread

from flask import Flask, jsonify, request
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

if slack_oauth_token is None:
    print("Configuration values not defined, please set your values in a config.json")
    sys.exit(1)

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
    content = request.form
    thread = Thread(target=do_matrix, args=(content,))
    thread.start()
    return jsonify({'response_type': "in_channel"})


def do_matrix(content):
    channel_id = content["channel_id"]
    response_url = content["response_url"]
    response = try_api_call("conversations.members", channel=channel_id)
    channel_members = response["members"]
    user_names = list(map(get_name_from_user_id, channel_members))
    rotated_user_names = user_names[1:] + user_names[:1]
    pairs = [(user_names[x], rotated_user_names[x]) for x in range(len(user_names))]
    payload = {'token': slack_oauth_token,
               'response_type': 'in_channel',
               'text': pprint_pairs(pairs),
               'attachments': []}
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


if __name__ == "__main__":
    app.run(host="localhost")
