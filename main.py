from myflask.flaskslack import FlaskSlack
from myslack.slack import ResponseType

flask_slack = FlaskSlack(__name__)
slack = flask_slack.slack


@flask_slack.slack_route('/slack/matrix', response_type=ResponseType.IN_CHANNEL, verify_signature=True)
def do_matrix(content):
    channel_id = content["channel_id"]
    response = slack.try_api_call("conversations.members", channel=channel_id)
    channel_members = response["members"]
    user_names = list(map(get_name_from_user_id, channel_members))
    rotated_user_names = user_names[1:] + user_names[:1]
    pairs = [(user_names[x], rotated_user_names[x]) for x in range(len(user_names))]
    payload = {'text': pprint_pairs(pairs)}
    return payload


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
    flask_slack.run(host="localhost")
