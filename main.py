from dataclasses import dataclass
from random import shuffle
from typing import List

import requests
from bs4 import BeautifulSoup
from flask import Flask
from flaskslack.attachment import Attachment, ButtonAttachment, Action
from flaskslack.flaskslack import FlaskSlack
from flaskslack.slack import ResponseType, Slack
from htmlslacker import HTMLSlacker
from mashumaro import DataClassDictMixin


app = Flask(__name__)
slack = Slack.create()
flask_slack = FlaskSlack(app, slack)


@dataclass
class Trivia(DataClassDictMixin):
    category: str
    type: str
    difficulty: str
    question: str
    correct_answer: str
    incorrect_answers: List[str]

    def create_actions(self) -> List[Action]:
        correct_answer = Action(name="c", text=self.correct_answer, value="Correct")
        answers = list(map(lambda x: Action(name="inc", text=x, value="Incorrect"), self.incorrect_answers))
        answers.append(correct_answer)
        shuffle(answers)
        return answers

    def as_button_attachment(self) -> ButtonAttachment:
        return ButtonAttachment(text=self.question,
                                actions=self.create_actions(),
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


@flask_slack.slack_route('/slack/trivia', response_type=ResponseType.IN_CHANNEL)
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
    trivia_dict_clean = dict((key, HTMLSlacker(value).get_output())
                             for key, value in trivia_dict.items())

    trivia = Trivia.from_dict(trivia_dict_clean)
    button_attachment = trivia.as_button_attachment()
    return Slack.create_response(text="", attachments=[button_attachment])


@flask_slack.slack_route('/slack/cafe', response_type=ResponseType.IN_CHANNEL)
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
    return Slack.create_response(text="", attachments=attachments)


@flask_slack.slack_route('/slack/matrix', response_type=ResponseType.IN_CHANNEL)
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
