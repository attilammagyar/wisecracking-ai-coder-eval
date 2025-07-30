import base64
import http.server
import json
import math
import os
import subprocess
import sys
import tempfile


"""
An HTTP server to conveniently run semi-untrusted Python code en-masse. Please
never run this script outside of a safe sandbox.

WARNING: never run this script in an environment which is exposed to the
         public internet!

Usage example:

    Inside the sandbox (slight adjustment may be needed; if you know what you
    are doing then this shouldn't be a problem - if it is, then you should
    really not run this script anywhere):

        python3 exec-server.py 127.0.0.1 3932 dQw4w9WgXcQ

    In a Jupyter notebook, after defining `sandbox.local` in your hosts file:

        import requests

        response = requests.post(
            'http://sandbox.local:3932',
            headers={"Authorization": "dQw4w9WgXcQ"},
            json={
                "timeout": 5.0,
                "script": "print('Hello, World!')"
            },
        )
        print(response.json())
"""


def main(argv):
    address = "127.0.0.1" if len(argv) < 2 else argv[1]
    port = 3932 if len(argv) < 3 else int(argv[2])  # telephone letters: e, x, e, c

    if len(argv) < 4:
        token = base64.b64encode(os.urandom(9)).decode("utf-8").replace("+", "_")
    else:
        token = argv[3]

    ExecRequestHandler.AUTH = token
    server = http.server.HTTPServer((address, port), ExecRequestHandler)

    print(f"""\
Serving at http://{address}:{port}, Authorization: {token}

curl -X POST http://{address}:{port} \\
    -H 'Authorization: {token}' \\
    -H 'Content-Type: application/json' \\
    -d @- \\
<<JSON
{{
    "timeout": 5,
    "script": "print(\\"Hello, World!\\")"
}}
JSON

""")
    server.serve_forever()

    return 0


class ExecRequestHandler(http.server.BaseHTTPRequestHandler):
    AUTH = None
    ERROR_TPL = (
        '; expected a JSON object in the following format: '
        ' {"script": "print(\"Hello, World!\")", "timeout": 5.0}'
    )

    def do_POST(self):
        try:
            script, timeout = self._parse_request()
            exit_code, stdout, stderr = self._exec(script, timeout)
            self._send_json_response(
                200,
                {"exit_code": exit_code, "stdout": stdout, "stderr": stderr}
            )
            self.log_message(f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}")

        except Exception as exc:
            msg = f"{type(exc)}: {exc}"
            self._send_json_response(400, {"error": msg})
            self.log_message(f"ERROR: {msg}")

    def _parse_request(self):
        auth = self.headers.get("Authorization", "")

        assert auth == self.AUTH, "Unauthorized"

        content_length = int(self.headers.get("Content-Length", -1))
        raw_request_body = self.rfile.read(content_length)
        request_body = json.loads(raw_request_body.decode("utf-8").strip())
        script = request_body.get("script", None)
        timeout = float(request_body.get("timeout", None))

        assert isinstance(script, str), "Missing or invalid script"
        assert timeout > 0.0, f"Timeout must be positive; {timeout=}"
        assert math.isfinite(timeout), f"Timeout must be finite; {timeout=}"

        return script, timeout

    def _exec(self, script, timeout):
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            try:
                f.write(script.encode("utf-8"))
                f.close()

                result = subprocess.run(
                    ["python3", f.name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=timeout,
                    text=True,
                )

            except Exception as exc:
                return -1, "", f"{type(exc)}: {exc}"

            finally:
                os.unlink(f.name)

        return result.returncode, result.stdout, result.stderr

    def _send_json_response(self, status, data):
        response_json = json.dumps(data, indent=2)

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_json)))
        self.end_headers()

        self.wfile.write(response_json.encode("utf-8"))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
