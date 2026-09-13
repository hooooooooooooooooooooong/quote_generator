from flask import Flask, jsonify, render_template
import random

app = Flask(__name__)

QUOTES = [
    "오늘 하루도 최선을 다한 당신, 정말 멋져요.",
    "작은 한 걸음이 결국 큰 변화를 만듭니다.",
    "완벽하지 않아도 괜찮아요, 계속 나아가는 게 중요해요.",
    "오늘의 운세: 뜻밖의 행운이 당신을 찾아올 거예요!",
    "가장 어두운 밤도 끝나면 해가 뜬다.",
    "지금 이 순간에 집중하세요, 그게 최선이에요.",
    "실패는 성공으로 가는 또 다른 이름입니다.",
    "당신의 노력은 반드시 결실을 맺을 거예요.",
    "오늘의 운세: 새로운 인연이 찾아올 좋은 날이에요.",
    "쉬어가는 것도 앞으로 나아가는 방법 중 하나입니다.",
]

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/random")
def random_quote():
    return jsonify({"quote": random.choice(QUOTES)})

if __name__ == "__main__":
    app.run(debug=True)
    