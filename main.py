from flask import Flask
from flaskslack.flaskslack import FlaskSlack
from flaskslack.slack import ResponseType, Slack

app = Flask(__name__)
slack = Slack.create()
flask_slack = FlaskSlack(app, slack)


@flask_slack.slack_route('/slack/matrix', response_type=ResponseType.IN_CHANNEL, verify_signature=False)
def do_matrix(content):
    channel_id = content["channel_id"]
    response = slack.try_api_call("conversations.members", channel=channel_id)
    channel_members = response["members"]
    user_names = list(map(get_name_from_user_id, channel_members))
    rotated_user_names = user_names[1:] + user_names[:1]
    pairs = [(user_names[x], rotated_user_names[x]) for x in range(len(user_names))]
    text_response = pprint_pairs(pairs)
    return Slack.create_response(text_response)


def pprint_pairs(pairs):
    str_list = ['```']
    for pair in pairs:
        str_list.append("{:30} | {:30}".format(pair[0], pair[1]))
    str_list.append("```")
    return "\n".join(str_list)


def get_name_from_user_id(user_id):
    response = slack.try_api_call("users.info", user=user_id)
    return response["user"]["real_name"]


if __name__ == "__main__":
    app.run(host="localhost")
