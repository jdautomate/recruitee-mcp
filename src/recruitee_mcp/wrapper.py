from flask import Flask, request, jsonify
import requests
import os
import logging

app = Flask(__name__)

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Config from environment
RECRUITEE_API = os.getenv("RECRUITEE_BASE_URL", "https://openvpn.recruitee.com/mcp")
API_TOKEN = os.getenv("RECRUITEE_API_TOKEN", "Mm4rL2ZoVzY1anpXaExmNVJ6WkkwZz09")

request_id = 1


def call_recruitee(method: str, params: dict):
    """Wraps params in JSON-RPC 2.0 and sends to Recruitee MCP API."""
    global request_id
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": request_id,
    }
    request_id += 1

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_TOKEN}",  # ✅ Auth header
    }

    logging.debug(f"➡️ Sending to Recruitee: {payload}")

    response = requests.post(RECRUITEE_API, json=payload, headers=headers)
    logging.debug(f"⬅️ Status: {response.status_code}, Response: {response.text}")

    response.raise_for_status()
    return response.json()


@app.route("/list_offers", methods=["POST"])
def list_offers():
    params = request.json or {}
    try:
        result = call_recruitee("list_offers", params)
        return jsonify(result)
    except Exception as e:
        logging.error(f"list_offers failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/get_offer", methods=["POST"])
def get_offer():
    params = request.json or {}
    try:
        result = call_recruitee("get_offer", params)
        return jsonify(result)
    except Exception as e:
        logging.error(f"get_offer failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/list_candidates", methods=["POST"])
def list_candidates():
    params = request.json or {}
    try:
        result = call_recruitee("list_candidates", params)
        return jsonify(result)
    except Exception as e:
        logging.error(f"list_candidates failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/search_candidates", methods=["POST"])
def search_candidates():
    params = request.json or {}
    try:
        result = call_recruitee("search_candidates", params)
        return jsonify(result)
    except Exception as e:
        logging.error(f"search_candidates failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/get_candidate", methods=["POST"])
def get_candidate():
    params = request.json or {}
    try:
        result = call_recruitee("get_candidate", params)
        return jsonify(result)
    except Exception as e:
        logging.error(f"get_candidate failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/create_candidate", methods=["POST"])
def create_candidate():
    params = request.json or {}
    try:
        result = call_recruitee("create_candidate", params)
        return jsonify(result)
    except Exception as e:
        logging.error(f"create_candidate failed: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(port=8080, debug=True)
