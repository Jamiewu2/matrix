from flask import Flask, jsonify, request
app = Flask(__name__)


@app.route('/')
def hello_world():
    return "Hello World"


@app.route('/post/<string:post_id>')
def show_post(post_id):
    return 'Post %s' % post_id


if __name__ == "__main__":
    app.run(host="localhost")
