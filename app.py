from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return "Akash is running!"

@app.route('/health')
def health():
    # AWS Load Balancer will use this to check if the app is alive
    return jsonify(status="healthy"), 200

@app.route('/validate', methods=['POST'])
def validate_transaction():
    data = request.json
    amount = data.get('amount')

    # Simple Logic: Transaction is valid if amount is positive and < 10000
    if amount and 0 < amount < 10000:
        return jsonify(valid=True, message="Transaction Approved"), 200
    else:
        return jsonify(valid=False, message="Transaction Rejected"), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)