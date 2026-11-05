"""Utilities for isolated PostgreSQL integration tests."""
from contextlib import contextmanager
from pathlib import Path
import os
import shutil
import socket
import subprocess
import tempfile


def postgres_bin(argument=None):
    if argument:
        result = Path(argument).resolve()
    elif os.environ.get("Z8_PG_BIN"):
        result = Path(os.environ["Z8_PG_BIN"]).resolve()
    elif shutil.which("pg_config"):
        result = Path(subprocess.check_output(["pg_config", "--bindir"], text=True).strip())
    else:
        raise SystemExit("Pass the PostgreSQL bin directory or set Z8_PG_BIN")
    suffix = ".exe" if os.name == "nt" else ""
    if not (result / ("initdb" + suffix)).is_file() or not (result / ("pg_ctl" + suffix)).is_file():
        raise SystemExit("PostgreSQL initdb and pg_ctl were not found")
    if os.name == "nt" and not (result.parent / "lib/libpq.lib").is_file():
        raise SystemExit("PostgreSQL libpq.lib was not found")
    return result


@contextmanager
def temporary_postgres(bin_dir):
    suffix = ".exe" if os.name == "nt" else ""
    initdb, pg_ctl = bin_dir / ("initdb" + suffix), bin_dir / ("pg_ctl" + suffix)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        data = temp / "data"
        subprocess.run([str(initdb), "-D", str(data), "-A", "trust", "-U", "postgres", "--no-locale", "-E", "UTF8", "--no-sync"],
                       env=env, stdout=subprocess.DEVNULL, check=True, creationflags=flags)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        try:
            options = f"-h 127.0.0.1 -p {port} -c fsync=off -c synchronous_commit=off -c full_page_writes=off"
            subprocess.run([str(pg_ctl), "-D", str(data), "-l", str(temp / "postgres.log"), "-o", options, "-w", "start"],
                           env=env, stdout=subprocess.DEVNULL, check=True, creationflags=flags)
            yield f"host=127.0.0.1 port={port} dbname=postgres user=postgres connect_timeout=5", env
        finally:
            if (data / "postmaster.pid").exists():
                subprocess.run([str(pg_ctl), "-D", str(data), "-m", "immediate", "-w", "stop"],
                               env=env, stdout=subprocess.DEVNULL, check=True, creationflags=flags)
