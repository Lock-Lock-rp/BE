from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 이거 반드시 있어야 함

@app.route('/api/test')
def test():
    return jsonify({"message": "CORS OK!", "success": True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
