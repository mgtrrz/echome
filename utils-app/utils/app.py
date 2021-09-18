from flask import Flask

app = Flask(__name__)

@app.route("/")
def front_page():
    return {}

@app.route("/health")
def health_check():
    return {"status": "ok"}

@app.route("/qemu-img")
def update_notion():
    return update_notion()

if __name__ == '__main__':
    app.run(debug = False, port = 8080, host = '0.0.0.0', threaded = True)