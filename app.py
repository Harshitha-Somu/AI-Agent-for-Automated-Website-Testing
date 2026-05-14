import os
import time
import json
import traceback
from flask import Flask, request, jsonify, send_from_directory, send_file

from agent.base_agent import create_agent
from database import init_db, save_run_history, get_run_history
from report_generator import generate_pdf_report

# -----------------------------------
# FLASK APP SETUP
# -----------------------------------
app = Flask(__name__, static_folder="static")


# -----------------------------------
# HOME PAGE
# -----------------------------------
@app.route("/")
def home():
    return send_from_directory("static", "index.html")


# -----------------------------------
# RUN HISTORY API
# -----------------------------------
@app.route("/api/history", methods=["GET"])
def api_history():
    try:
        history = get_run_history(limit=10)
        return jsonify(history if history else [])
    except Exception:
        return jsonify([])


# -----------------------------------
# RUN TEST API
# -----------------------------------
@app.route("/api/run_test", methods=["POST"])
def api_run_test():
    try:
        payload = request.get_json(force=True)

        instruction = payload.get("instruction", "")
        target = payload.get("target", "")
        mode = payload.get("mode", "execute")

        agent = create_agent()

        # Run agent
        raw_result = agent.invoke({
            "instruction": instruction,
            "target": target,
            "mode": mode
        })

        # Create unified report structure
        report = {
            "id": "RUN_" + str(int(time.time() * 1000)),
            "instruction": instruction,
            "target": target,
            "status": raw_result.get("status", "executed"),
            "duration": raw_result.get("duration", 0),
            "total_steps": raw_result.get("total_steps", 0),
            "passed_steps": raw_result.get("passed_steps", 0),
            "failed_steps": raw_result.get("failed_steps", 0),
            "step_results": raw_result.get("step_results", [])
        }

        # Save to database
        save_run_history(instruction, target, mode, report)

        # IMPORTANT: wrap inside "result" for frontend
        return jsonify({"result": report})

    except Exception as e:

        tb = traceback.format_exc()

        print("========== ERROR ==========")
        print(tb)
        print("===========================")

        return jsonify({
            "result": {
                "id": "ERR",
                "status": "error",
                "duration": 0,
                "total_steps": 0,
                "passed_steps": 0,
                "failed_steps": 0,
                "step_results": [],
                "message": str(e),
                "traceback": tb
            }
        }), 500


# -----------------------------------
# DOWNLOAD JSON REPORT
# -----------------------------------
@app.route("/api/download/json/<run_id>")
def download_json(run_id):
    history = get_run_history(limit=20)

    for run in history:
        report = run.get("full_report", {})
        if str(report.get("id")) == run_id:
            os.makedirs("static/reports", exist_ok=True)
            path = f"static/reports/{run_id}.json"

            with open(path, "w") as f:
                json.dump(report, f, indent=2)

            return send_file(path, as_attachment=True)

    return "Report not found", 404


# -----------------------------------
# DOWNLOAD PDF REPORT
# -----------------------------------
@app.route("/api/download/pdf/<run_id>")
def download_pdf(run_id):
    history = get_run_history(limit=20)

    for run in history:
        report = run.get("full_report", {})
        if str(report.get("id")) == run_id:
            os.makedirs("static/reports", exist_ok=True)
            pdf_path = f"static/reports/{run_id}.pdf"

            generate_pdf_report(report, pdf_path)

            return send_file(pdf_path, as_attachment=True)

    return "Report not found", 404


# -----------------------------------
# APP ENTRY POINT
# -----------------------------------
# Initialize database
init_db()

# Ensure folders exist
os.makedirs("static/screenshots", exist_ok=True)
os.makedirs("static/reports", exist_ok=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)