import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import assistant


ROOT = Path(__file__).parent
FRONTEND = ROOT / "frontend"


class AssistantHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    def do_POST(self):
        if self.path == "/listen":
            question, error = assistant.listen_for_voice()
            if error:
                self.send_json({"error": error}, status=502)
            else:
                self.send_json({"question": question})
            return

        if self.path != "/ask":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length))
            question = str(payload.get("question", "")).strip()
            if not question:
                raise ValueError("Question is empty")
            answer = assistant.process_command(question, speak_response=False)
            self.send_json({"answer": answer or "I am ready for your next question."})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, status=400)
        except Exception:
            self.send_json({"error": "The assistant could not process that request."}, status=500)

    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(f"Web: {format % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), AssistantHandler)
    print("Ultron is running at http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nUltron stopped.")
    finally:
        server.server_close()
