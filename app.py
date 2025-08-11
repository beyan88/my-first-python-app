from flask import Flask, request

app = Flask(__name__)

# トップページ
@app.route("/")
def index():
    return """
    <h1>簡単な足し算アプリ</h1>
    <form action="/calculate" method="post">
        <input type="number" name="num1" required> +
        <input type="number" name="num2" required>
        <button type="submit">計算</button>
    </form>
    """

# 計算結果を表示するページ
@app.route("/calculate", methods=["POST"])
def calculate():
    # フォームから値を取得
    num1 = float(request.form["num1"])
    num2 = float(request.form["num2"])

    # 足し算を実行
    result = num1 + num2

    return f"""
    <h1>計算結果</h1>
    <p>{num1} + {num2} = {result}</p>
    <a href="/">戻る</a>
    """

if __name__ == "__main__":
    app.run(debug=True)
