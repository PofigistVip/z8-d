"""Build and exercise the example BL application with a real PostgreSQL server."""
from pathlib import Path
import http.client
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
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
    config = temp / "custom.properties"
    config.write_text("application.working.path=work\nstorage.path=storage-data\nstorage.path.format=yyyy/MM\nsecurity.log.file=logs/security.log\nweb.client.hashPassword=false\nfiles.saveOnDisk=true\nauth.fails.limit=2\nauth.fails.banSeconds=60\nauthority.center.session.onePerUser=true\nauthority.center.session.timeout=10\n", encoding="ascii")
    default_config = temp / "server.properties"
    default_config.write_text("web.client.hashPassword=true\n", encoding="ascii")
    subprocess.run([sys.executable, str(root / "webserver/prepare_client.py"), str(Path(sys.argv[1]).resolve()), str(public)], check=True)

    with temporary_postgres(bin_dir) as (connection, environment):
        init = subprocess.run([str(executable), connection, "public", "--initialize", "--config", str(config)], env=environment,
                              capture_output=True, text=True, encoding="utf-8", check=True)
        assert init.stdout.strip() == "initialized", init.stdout
        psql = bin_dir / ("psql.exe" if os.name == "nt" else "psql")
        subprocess.run([str(psql), "-v", "ON_ERROR_STOP=1", "-c",
                        '''UPDATE "SystemUsers" SET "Password"=md5('example-secret') WHERE "RecordId"='00000000-0000-0000-0000-000000000002' ''', connection],
                       env=environment, capture_output=True, check=True)
        subprocess.run([str(executable), connection, "public", "--initialize", "--config", str(config)], env=environment,
                       capture_output=True, text=True, encoding="utf-8", check=True)
        subprocess.run([str(psql), "-v", "ON_ERROR_STOP=1", "-c",
                        '''UPDATE "SystemScheduledJobs" SET "Cron"='* * * * *', "Active"=1, "Log errors only"=0 WHERE "Job"=(SELECT "RecordId" FROM "SystemJobs" WHERE "Class"='TasksJob')''', connection],
                       env=environment, capture_output=True, check=True)

        def start(explicit_config=False):
            command = [str(executable), connection, "public", "--public-dir", str(public)]
            if explicit_config:
                command.extend(["--config", str(config)])
            process = subprocess.Popen(command, cwd=temp, env=environment,
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

        process, port = start(explicit_config=True)
        try:
            deadline = time.monotonic() + 15
            while True:
                count = subprocess.check_output([str(psql), "-tAc", 'SELECT count(*) FROM "SystemScheduledJobLogs" WHERE "Errors"=0 AND "ScheduledJob" <> \'00000000-0000-0000-0000-000000000000\'', connection], env=environment, text=True).strip()
                if int(count) > 0:
                    break
                if time.monotonic() >= deadline:
                    raise AssertionError("Scheduled job did not finish successfully")
                time.sleep(0.2)
            logs = subprocess.check_output([str(psql), "-tAc", 'SELECT convert_from("Files", \'UTF8\') FROM "SystemScheduledJobLogs" WHERE "Errors"=0 AND "ScheduledJob" <> \'00000000-0000-0000-0000-000000000000\' LIMIT 1', connection], env=environment, text=True).strip()
            log_path = Path(json.loads(logs)[0]["path"])
            assert log_path.is_relative_to(temp / "work/logs/scheduler") and "Tasks scheduled job ran" in log_path.read_text(encoding="utf-8")
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
            password = "example-secret"
            assert browser_login(port, "Admin", "wrong")[0] == 401
            assert browser_login(port, "Admin", "wrong")[0] == 401
            assert browser_login(port, "Admin", password)[0] == 401
            subprocess.run([str(psql), "-v", "ON_ERROR_STOP=1", "-c",
                            '''UPDATE "SystemUsers" SET "Banned Until"=0, "Failed Auth Count"=0 WHERE "RecordId"='00000000-0000-0000-0000-000000000002' ''', connection],
                           env=environment, capture_output=True, check=True)
            status, login = browser_login(port, "Admin", password)
            assert status == 200 and login["success"], login
            assert sum(entry["request"] == "Tasks" for entry in login["user"]["entries"]) == 1, login
            tools_class = "org.zenframework.z8.server.base.table.system.SystemTools"
            files_view = "org.zenframework.z8.server.base.table.system.view.FilesView"
            sequences_view = "org.zenframework.z8.server.base.table.system.view.SequencesView"
            tables_view = "org.zenframework.z8.server.base.table.system.view.TablesView"
            jobs_view = "org.zenframework.z8.server.base.table.system.view.JobsView"
            roles_view = "org.zenframework.z8.server.base.table.system.view.RoleTableAccessView"
            users_view = "org.zenframework.z8.server.base.table.system.view.UsersView"
            assert any(entry["request"] == tools_class for entry in login["user"]["entries"]), login
            assert any(item.get("request") == files_view for group in login["user"]["data"] for item in group.get("items", [])), login
            assert any(item.get("request") == sequences_view for group in login["user"]["data"] for item in group.get("items", [])), login
            assert any(item.get("request") == tables_view for group in login["user"]["data"] for item in group.get("items", [])), login
            assert any(item.get("request") == jobs_view for group in login["user"]["data"] for item in group.get("items", [])), login
            assert any(item.get("request") == roles_view for group in login["user"]["data"] for item in group.get("items", [])), login
            assert any(item.get("request") == users_view for group in login["user"]["data"] for item in group.get("items", [])), login
            session = login["session"]
            status, replacement = browser_login(port, "Admin", password)
            assert status == 200 and replacement["success"] and replacement["session"] != session
            assert request(port, request="login", session=session)[0] == 401
            session = replacement["session"]
            status, files_metadata = request(port, request=files_view, session=session, action="meta")
            assert status == 200 and files_metadata["success"] and [item["name"] for item in files_metadata["controls"]] == ["name", "createdAt", "path"], files_metadata
            status, sequences_metadata = request(port, request=sequences_view, session=session, action="meta")
            assert status == 200 and sequences_metadata["success"] and [item["name"] for item in sequences_metadata["controls"]] == ["key", "value", "description"], sequences_metadata
            status, tables_metadata = request(port, request=tables_view, session=session, action="meta")
            assert status == 200 and tables_metadata["success"] and [item["name"] for item in tables_metadata["controls"]] == ["classId", "name", "displayName", "description", "fieldsListbox"], tables_metadata
            fields_list = tables_metadata["controls"][-1]["query"]
            assert fields_list["name"] == "fields" and fields_list["link"]["name"] == "fields.table", fields_list
            assert [item["name"] for item in fields_list["columns"]] == ["fields.name", "fields.type", "fields.displayName", "fields.description"], fields_list
            status, jobs_metadata = request(port, request=jobs_view, session=session, action="meta")
            assert status == 200 and jobs_metadata["success"] and [item["name"] for item in jobs_metadata["controls"]] == ["jobs.name", "users.name", "cron", "active", "logErrorsOnly", "lastStart", "lastFinish", "nextStart", "logsListbox"], jobs_metadata
            logs_list = jobs_metadata["controls"][-1]["query"]
            assert logs_list["name"] == "logs" and logs_list["link"]["name"] == "logs.scheduledJob", logs_list
            assert [item["name"] for item in logs_list["columns"]] == ["logs.start", "logs.finish", "logs.errors", "logs.file", "logs.fileSize", "logs.description"], logs_list
            assert any(action["name"] == "restartScheduler" for action in jobs_metadata["actions"]), jobs_metadata
            status, restarted = request(port, request=jobs_view, session=session, action="action", name="restartScheduler", records="[]", selection="[]", parameters="[]")
            assert status == 200 and restarted["success"], restarted
            status, roles_metadata = request(port, request=roles_view, session=session, action="meta")
            assert status == 200 and roles_metadata.get("success") and [item["name"] for item in roles_metadata.get("controls", [])] == ["name", "tablesListbox", "fieldsListbox", "requestsListbox"], roles_metadata
            tables_rights = roles_metadata["controls"][1]["query"]
            fields_rights = roles_metadata["controls"][2]["query"]
            requests_rights = roles_metadata["controls"][3]["query"]
            assert tables_rights["name"] == "rta" and tables_rights["link"]["name"] == "rta.role", tables_rights
            assert fields_rights["name"] == "rfa" and fields_rights["link"]["name"] == "rfa.role", fields_rights
            assert requests_rights["name"] == "rra" and requests_rights["link"]["name"] == "rra.role", requests_rights
            role_access_id = subprocess.check_output([str(psql), "-tAc", '''SELECT a."RecordId" FROM "SystemRoleTableAccess" a JOIN "SystemTables" t ON t."RecordId"=a."Table" WHERE t."Name"='Tasks' AND a."Role"='421A8413-A8EC-4DAB-9235-9A5FF83341C5' ''', connection], env=environment, text=True).strip()
            assert role_access_id
            status, rights_changed = request(port, request=roles_view, session=session, action="update", query="rta",
                                             fields='["rta.read"]', data=json.dumps([{"rta.recordId": role_access_id, "rta.read": False}]))
            assert status == 200 and rights_changed["success"] and not rights_changed["data"][0]["rta.read"], rights_changed
            updated_right = subprocess.check_output([str(psql), "-tAc", '''SELECT "Read" FROM "SystemRoleTableAccess" WHERE "RecordId"=''' + "'" + role_access_id + "'", connection], env=environment, text=True).strip()
            assert updated_right == "0", updated_right
            status, users_metadata = request(port, request=users_view, session=session, action="meta")
            assert status == 200 and users_metadata["success"] and [item["name"] for item in users_metadata.get("controls", [])] == ["form"], users_metadata
            user_form = users_metadata["controls"][0]
            assert any(item["name"] == "form.resetPassword" for item in user_form.get("controls", [])), user_form
            status, new_user = request(port, request=users_view, session=session, action="create", fields='["name"]', data='[{"name":"Reset example","password":"abcdef0123456789abcdef0123456789"}]')
            assert status == 200 and new_user["success"], new_user
            user_id = new_user["data"][0]["recordId"]
            status, reset = request(port, request=users_view, session=session, action="action", name="form.resetPassword", records=json.dumps([user_id]), selection="[]", parameters="[]")
            assert status == 200 and reset["success"], reset
            reset_value = subprocess.check_output([str(psql), "-tAc", '''SELECT "Password" || ':' || "Change Password"::text FROM "SystemUsers" WHERE "RecordId"=''' + "'" + user_id + "'", connection], env=environment, text=True).strip()
            assert reset_value == "d41d8cd98f00b204e9800998ecf8427e:1", reset_value
            role_id = "421a8413-a8ec-4dab-9235-9a5ff83341c5"
            def available_roles(current_user):
                status, response = request(port, request=users_view, session=session, action="read",
                                           link="form.userRoles.role", fields='["form.userRoles.roles.name"]',
                                           values=json.dumps({"recordId": current_user}))
                assert status == 200 and response.get("success"), str(response)[:2000]
                return {row["form.userRoles.roles.recordId"].lower() for row in response["data"]}
            initial_roles = available_roles(user_id)
            assert role_id in initial_roles, initial_roles
            assignment = json.dumps([{"form.userRoles.user": user_id, "form.userRoles.role": "421a8413-a8ec-4dab-9235-9a5ff83341c5"}])
            status, assigned = request(port, request=users_view, session=session, action="create", query="form.userRoles", fields='["form.userRoles.user","form.userRoles.role"]', data=assignment)
            assert status == 200 and assigned["success"], assigned
            status, duplicate = request(port, request=users_view, session=session, action="create", query="form.userRoles", fields='["form.userRoles.user","form.userRoles.role"]', data=assignment)
            assert status == 200 and not duplicate["success"], duplicate
            assigned_count = subprocess.check_output([str(psql), "-tAc", '''SELECT count(*) FROM "SystemUserRoles" WHERE "User"=''' + "'" + user_id + "'", connection], env=environment, text=True).strip()
            assert assigned_count == "1", assigned_count
            assert role_id not in available_roles(user_id)
            assert role_id in available_roles("00000000-0000-0000-0000-000000000000")
            status, metadata = request(port, request="Tasks", session=session, action="meta")
            assert status == 200 and metadata["success"], metadata
            assert [control["name"] for control in metadata["controls"]] == ["title", "done", "documents"], metadata
            assert [column["name"] for column in metadata["columns"]] == ["title", "done"], metadata
            assert {field["name"] for field in metadata["fields"]} >= {"title", "done", "documents", "recordId"}, metadata
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
            assert re.match(r"^storage/\d{4}/\d{2}/Tasks/", files[0]["path"]), files[0]["path"]
            assert (temp / "work/storage-data" / files[0]["path"][len("storage/"):]).read_bytes() == b"first"
            location = subprocess.check_output([str(psql), "-tAc", 'SELECT "Location" FROM "SystemFiles" WHERE "RecordId" = ' + "'" + files[0]["id"] + "'", connection], env=environment, text=True).strip()
            assert location == "1", location
            assert download(port, files[0]["path"], session, files[0]["id"]) == b"first"
            status, archived = request(port, request="Tasks", session=session, action="archive", archive=json.dumps(files))
            assert status == 200 and archived["success"], archived
            with zipfile.ZipFile(io.BytesIO(download(port, archived["source"], session))) as archive:
                assert archive.read("first.txt") == b"first" and archive.read("second.txt") == bytes([0, 255, 42])
        finally:
            stop(process)
        audit = (temp / "work/logs/security.log").read_text(encoding="utf-8")
        assert "Action{login}" in audit and "Object{request:Tasks}" in audit and password not in audit

        default_config.write_bytes(config.read_bytes() + b"scheduler.enabled=false\n")
        subprocess.run([str(psql), "-v", "ON_ERROR_STOP=1", "-c",
                        '''UPDATE "SystemScheduledJobs" SET "LastStart"=0 WHERE "Job"=(SELECT "RecordId" FROM "SystemJobs" WHERE "Class"='TasksJob')''', connection],
                       env=environment, capture_output=True, check=True)
        process, port = start()
        try:
            assert request(port, request="login", session=session)[0] == 401
            status, login = request(port, request="login", login="Admin", password=password)
            assert status == 200 and login["success"], login
            session = login["session"]
            status, restarted = request(port, request=jobs_view, session=session, action="action", name="restartScheduler", records="[]", selection="[]", parameters="[]")
            assert status == 200 and restarted["success"], restarted
            time.sleep(2)
            last_start = subprocess.check_output([str(psql), "-tAc", '''SELECT "LastStart" FROM "SystemScheduledJobs" WHERE "Job"=(SELECT "RecordId" FROM "SystemJobs" WHERE "Class"='TasksJob')''', connection], env=environment, text=True).strip()
            assert last_start == "0", last_start
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
