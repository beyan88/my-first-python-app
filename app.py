from flask import Flask

# Flaskアプリケーションのインスタンスを作成
app = Flask(__name__)

# トップページにアクセスしたときに実行される関数
@app.route("/")
def hello_world():
    return "Hello, Render!"

# アプリケーションをローカルで起動するための記述
if __name__ == "__main__":
    app.run(debug=True)
