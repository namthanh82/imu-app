from flask import Flask, render_template, request, jsonify
from chatbot import get_answer

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    question = data.get("message", "")
    if not question.strip():
        return jsonify({"answer": ""})
    answer = get_answer(question)
    return jsonify({"answer": answer})

if __name__ == "__main__":
    app.run(debug=True)