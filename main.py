import json
from dataclasses import dataclass, asdict
from enum import Enum
from random import shuffle
from threading import Thread
from typing import List

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request, abort, make_response
from flaskslack.attachment import Attachment, Field
# from flaskslack.flaskslack import FlaskSlack
from flaskslack.slack import ResponseType, Slack
from htmlslacker import HTMLSlacker
from mashumaro import DataClassDictMixin


def parameterized(dec):
    def layer(*args, **kwargs):
        def repl(f):
            return dec(f, *args, **kwargs)
        return repl
    return layer


def parameterized_decorator_instance(dec):
    """
    Meta-decorator that allows an instance method decorator to have parameters
    """
    def layer(self, *args, **kwargs):
        def repl(f):
            return dec(self, f, *args, **kwargs)
        return repl
    return layer


def delayed_message(func: callable, response_type: ResponseType):
    """
    Sends a POST request to the response_url located in the form_content.
    See: https://api.slack.com/slash-commands#sending_delayed_responses

    :param func: The actual implementation function that does the logic.
            It should return a dict. dict should contain 'text', and/or a list of 'attachments'.
            See: https://api.slack.com/slash-commands#responding_immediate_response
    :param response_type:
    :return:
    """

    def decorator(form_content: dict):

        # if response_url does not exist,
        # then the form_content might be wrapped inside a "payload"
        if "response_url" not in form_content:
            if "payload" not in form_content:
                raise ValueError("response_url or payload not in form_content")
            form_content = json.loads(form_content["payload"])

        response_url = form_content["response_url"]
        print(form_content)

        try:
            json_response = func(form_content)
        except Exception:
            error_json = {
                'text': "500 Internal Server Error: The server encountered an internal error and was unable to complete your request."
                        " Either the server is overloaded or there is an error in the application.",
                'response_type': ResponseType.EPHEMERAL.value
            }

            requests.post(response_url, json=error_json)
            raise
        else:
            # send a delayed response to response_url
            json_response['response_type'] = response_type.value
            requests.post(response_url, json=json_response)

    return decorator


class FlaskSlack:
    def __init__(self, app: 'Flask', slack: 'Slack' = Slack.create()):
        self.app = app
        self.slack = slack

    @parameterized_decorator_instance
    def slack_route(self, func: callable, route: str, response_type: ResponseType, verify_signature: bool=True, empty_immediate_response: bool=False):
        """
        a decorator method that wraps an implementation method to allow for receiving and responding to slack
        slash commands
        """

        @self.app.route(route, methods=['POST'], endpoint=route)  # TODO endpoint hack to fix name conflict
        def decorator():
            # verify that the request is from slack
            if verify_signature:
                try:
                    raw_body = request.get_data()
                    slack_request_timestamp = request.headers['X-Slack-Request-Timestamp']
                    slack_signature = request.headers['X-Slack-Signature']
                    if not self.slack.verify_signature(slack_request_timestamp, slack_signature, raw_body):
                        abort(400, {'message': 'slack verify signature failed'})
                except KeyError:
                    abort(400, {'message': 'slack verification headers missing'})

            # verification passed, handle request in another thread
            form_content = request.form
            delayed_message_func = delayed_message(func, response_type)
            thread = Thread(target=delayed_message_func, args=(form_content,))
            thread.start()

            # immediately return 200
            if empty_immediate_response:
                return make_response("", 200)
            else:
                return jsonify({"response_type": response_type.value})
        return decorator


app = Flask(__name__)
slack = Slack.create()
flask_slack = FlaskSlack(app, slack)


@dataclass
class Action(DataClassDictMixin):
    name: str = None
    text: str = None
    type: str = "button"
    value: str = None


@dataclass
class ButtonAttachment(Attachment):
    text: str = None
    fallback: str = "default fallback"
    callback_id: str = None
    color: str = "#123456"
    attachment_type: str = "default"
    actions: List[Action] = None
    confirm = None  # TODO confirm textbox
    footer: str = None

    def asdict(self):
        return asdict(self)


@dataclass
class Trivia(DataClassDictMixin):
    category: str
    type: str
    difficulty: str
    question: str
    correct_answer: str
    incorrect_answers: List[str]

    def tmp(self):
        c = self.incorrect_answers.copy()
        c.append(self.correct_answer)
        shuffle(c)
        return HTMLSlacker(', '.join(c)).get_output()

    def tmp2(self) -> List[Action]:
        correct_answer = Action(name="c", text=self.correct_answer, value="correct")
        answers = list(map(lambda x: Action(name="inc", text=x, value="incorrect"), self.incorrect_answers))
        answers.append(correct_answer)
        shuffle(answers)
        return answers

    def as_attachment(self):
        return Attachment(text=HTMLSlacker(self.question).get_output(),
                          fields= [Field(title="answers", value=self.tmp(), short=True)],
                          footer=f"{self.category} | {self.type} | {self.difficulty}")

    def as_attachment_v2(self) -> ButtonAttachment:
        return ButtonAttachment(text=HTMLSlacker(self.question).get_output(),
                          actions=self.tmp2(),
                          callback_id="trivia_id",
                          footer=f"{self.category} | {self.type} | {self.difficulty}")



@dataclass
class Cafe(DataClassDictMixin):
    title: str
    description: str

    def as_attachment(self):
        return Attachment(title=self.title, text=self.description)


@flask_slack.slack_route('/slack/action-endpoint', response_type=ResponseType.EPHEMERAL, empty_immediate_response=True)
def do_action_endpoint(content):
    value = content["actions"][0]["value"]
    return {'text': value, 'replace_original': False}


@flask_slack.slack_route('/slack/trivia', response_type=ResponseType.IN_CHANNEL, verify_signature=False)
def do_trivia(content):
    category_dict = {
        'general': 9,
        'books': 10,
        'film': 11,
        'music': 12,
        'musicals': 13,
        'tv': 14,
        'video games': 15,
        'board games': 16,
        'science': 17,
        'computers': 18,
        'math': 19,
        'mythology': 20,
        'sports': 21,
        'geography': 22,
        'history': 23,
        'politics': 24,
        'art': 25,
        'celebrities': 26,
        'animals': 27,
        'vehicles': 28,
        'comics': 29,
        'gadgets': 30,
        'anime': 31,
        'cartoons': 32
    }

    request_url = "https://opentdb.com/api.php?amount=1"

    # add category query param
    category = content["text"].lower()
    if category and category in category_dict:
        request_url += f"&category={category_dict[category]}"
    elif category == "help":
        help_message = "\n".join([f"/trivia {key}" for key in category_dict])
        return Slack.create_response(text=help_message)

    r = requests.get(request_url)
    trivia_dict = r.json()["results"][0]
    trivia = Trivia.from_dict(trivia_dict)
    button_attachment = trivia.as_attachment_v2().asdict()
    print(button_attachment)
    return {'attachments': [button_attachment]}
    # return Slack.create_response(text="", attachments=[trivia.as_attachment()])


@flask_slack.slack_route('/slack/cafe', response_type=ResponseType.IN_CHANNEL, verify_signature=True)
def do_cafe(content):
    page = requests.get("http://www.parkcafegreenwich.com/menu.php")
    soup = BeautifulSoup(page.content, "html.parser")

    name = soup.select('.CollapsiblePanelContent > div > b')
    description = soup.select('.CollapsiblePanelContent > div > font')
    first_item = name[0].get_text()
    first_description = description[0].get_text()
    name2 = soup.select('.CollapsiblePanelContent div p b')[0:4]
    description2 = soup.select('.CollapsiblePanelContent div p font')[0:4]
    name2_clean = [name2.get_text() for name2 in name2]
    description2_clean = [description2.get_text() for description2 in description2]
    name_final = [first_item] + name2_clean
    description_final = [first_description] + description2_clean

    zipped = zip(name_final, description_final)
    menu_items = map(lambda x: Cafe(title=x[0], description=x[1]), list(zipped))
    attachments = list(map(lambda x: x.as_attachment(), menu_items))
    print(attachments)
    return Slack.create_response(text="", attachments=attachments)


@flask_slack.slack_route('/slack/matrix', response_type=ResponseType.IN_CHANNEL, verify_signature=True)
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
