from flask import Flask

app = Flask(__name__)

@app.route("/")
def front_page():
    return {}

@app.route("/update-notion")
def update_notion():
    return update_notion()

if __name__ == '__main__':
    app.run(debug = False, port = 8080, host = '0.0.0.0', threaded = True)