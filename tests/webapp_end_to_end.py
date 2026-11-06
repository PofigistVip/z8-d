"""Build and exercise the example BL application with a real PostgreSQL server."""
from pathlib import Path
import hashlib
import http.client
import io
import json
import os
import subprocess
import sys
import tempfile
from urllib.parse import quote, urlencode
import zipfile

from postgres_support import postgres_bin, temporary_postgres

if len(sys.argv) not in (2, 3):
    raise SystemExit("Usage: python tests/webapp_end_to_end.py <original-z8-root> [postgres-bin-directory]")
root = Path(__file__).resolve().parents[1]
language = Path(sys.argv[1]).resolve() / "org.zenframework.z8.lang/src/bl"
if not language.is_dir():
    raise SystemExit("Original BL standard library not found")
bin_dir = postgres_bin(sys.argv[2] if len(sys.argv) == 3 else None)
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    executable = temp / ("webapp.exe" if os.name == "nt" else "webapp")
    subprocess.run([sys.executable, str(root / "examples/webapp/build.py"), str(Path(sys.argv[1]).resolve()),
                    str(executable), "--postgres-bin", str(bin_dir)], check=True)
    public = temp / "public"
    subprocess.run([sys.executable, str(root / "webserver/prepare_client.py"), str(Path(sys.argv[1]).resolve()), str(public)], check=True)

    with temporary_postgres(bin_dir) as (connection, environment):
        init = subprocess.run([str(executable), connection, "public", "--initialize"], env=environment,
                              capture_output=True, text=True, encoding="utf-8", check=True)
        assert init.stdout.strip() == "initialized", init.stdout
        psql = bin_dir / ("psql.exe" if os.name == "nt" else "psql")
        subprocess.run([str(psql), "-v", "ON_ERROR_STOP=1", "-c",
                        '''UPDATE "SystemUsers" SET "Password"=md5('example-secret') WHERE "RecordId"='00000000-0000-0000-0000-000000000002' ''', connection],
                       env=environment, capture_output=True, check=True)
        subprocess.run([str(executable), connection, "public", "--initialize"], env=environment,
                       capture_output=True, text=True, encoding="utf-8", check=True)

        def start():
            process = subprocess.Popen([str(executable), connection, "public", "--public-dir", str(public)], cwd=temp, env=environment,
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
            line = process.stdout.readline().strip()
            if not line.isdigit():
                raise RuntimeError("Example server did not start: " + line + process.stderr.read())
            return process, int(line)

        def stop(process):
            process.stdin.write("\n"); process.stdin.flush()
            process.wait(timeout=15)
            if process.returncode:
                raise RuntimeError("Example server failed: " + process.stderr.read())

        def request(port, **params):
            client = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            try:
                client.request("GET", "/request.json?" + urlencode(params))
                response = client.getresponse()
                return response.status, json.loads(response.read())
            finally:
                client.close()

        def browser_login(port, login, password):
            params = {"request": "login", "login": login, "password": password, "experimental": "true"}
            boundary = "z8-browser-login"
            body = b""
            for key, value in params.items():
                body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n').encode()
            body += f"--{boundary}--\r\n".encode()
            client = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            try:
                client.request("POST", "/request.json", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})
                response = client.getresponse()
                return response.status, json.loads(response.read())
            finally:
                client.close()

        def upload(port, session, record, name, data):
            params = {"request": "Tasks", "session": session, "action": "attach", "field": "documents",
                      "recordId": record, "fields": '["title","documents"]'}
            boundary = "z8-example-upload"
            body = b""
            for key, value in params.items():
                body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n').encode()
            body += (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
                     'Content-Type: application/octet-stream\r\n\r\n').encode() + data + b"\r\n"
            body += f"--{boundary}--\r\n".encode()
            client = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            try:
                client.request("POST", "/request.json", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})
                response = client.getresponse(); result = json.loads(response.read())
                assert response.status == 200 and result["success"], result
                return json.loads(result["data"][0]["documents"])
            finally:
                client.close()

        def download(port, path, session, file_id=None):
            params = {"session": session}
            if file_id is not None:
                params["id"] = file_id
            client = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            try:
                client.request("GET", "/" + quote(path, safe="/") + "?&" + urlencode(params))
                response = client.getresponse(); data = response.read()
                assert response.status == 200, (response.status, data)
                return data
            finally:
                client.close()

        process, port = start()
        try:
            client = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            try:
                client.request("GET", "/index.html")
                response = client.getresponse(); page = response.read()
                assert response.status == 200 and page == (public / "index.html").read_bytes()
            finally:
                client.close()
            client = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            try:
                client.request("GET", "/revolt.js")
                response = client.getresponse(); script = response.read()
                assert response.status == 200 and script == (public / "revolt.js").read_bytes()
            finally:
                client.close()
            password = hashlib.md5(b"example-secret").hexdigest()
            status, login = browser_login(port, "Admin", password)
            assert status == 200 and login["success"], login
            assert sum(entry["request"] == "Tasks" for entry in login["user"]["entries"]) == 1, login
            session = login["session"]
            status, metadata = request(port, request="Tasks", session=session, action="meta")
            assert status == 200 and metadata["success"], metadata
            status, created = request(port, request="Tasks", session=session, action="create", fields='["title","done"]',
                                      data='[{"title":"First task","done":false}]')
            assert status == 200 and created["success"], created
            record = created["data"][0]["recordId"]
            status, updated = request(port, request="Tasks", session=session, action="update", fields='["title","done"]',
                                      data=json.dumps([{"recordId": record, "done": True}]))
            assert status == 200 and updated["success"] and updated["data"][0]["done"], updated
            files = upload(port, session, record, "first.txt", b"first")
            files = upload(port, session, record, "second.txt", bytes([0, 255, 42]))
            assert len(files) == 2
            assert download(port, files[0]["path"], session, files[0]["id"]) == b"first"
            status, archived = request(port, request="Tasks", session=session, action="archive", archive=json.dumps(files))
            assert status == 200 and archived["success"], archived
            with zipfile.ZipFile(io.BytesIO(download(port, archived["source"], session))) as archive:
                assert archive.read("first.txt") == b"first" and archive.read("second.txt") == bytes([0, 255, 42])
        finally:
            stop(process)

        process, port = start()
        try:
            assert request(port, request="login", session=session)[0] == 401
            status, login = request(port, request="login", login="Admin", password=password)
            assert status == 200 and login["success"], login
            session = login["session"]
            status, rows = request(port, request="Tasks", session=session, action="read", fields='["title","done","documents"]')
            assert status == 200 and rows["success"] and len(rows["data"]) == 1, rows
            files = json.loads(rows["data"][0]["documents"])
            assert rows["data"][0]["title"] == "First task" and rows["data"][0]["done"] and len(files) == 2, rows
            assert download(port, files[1]["path"], session, files[1]["id"]) == bytes([0, 255, 42])
            status, detached = request(port, request="Tasks", session=session, action="detach", field="documents", recordId=record,
                                       fields='["documents"]', data=json.dumps([files[0]["id"]]))
            assert status == 200 and detached["success"] and len(json.loads(detached["data"][0]["documents"])) == 1, detached
        finally:
            stop(process)
print("Generated BL application, PostgreSQL bootstrap, HTTP files and restart verified")
