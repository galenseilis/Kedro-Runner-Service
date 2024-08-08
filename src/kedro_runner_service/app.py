from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from cerberus import Validator
from queue import Queue, Full
import subprocess
import os
import yaml
import sqlite3
import time
from multiprocessing import Process, Queue as MPQueue, Lock
from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData

app = FastAPI()

# Configurations
CONFIG_FILE = "kedro_projects.yaml"
QUEUE_CAPACITY = 1000  # Default queue capacity
NUM_SERVERS = 1  # Default number of concurrent servers
DEFAULT_DB_PATH = "requests.db"

# A FIFO queue to hold incoming requests using multiprocessing
request_queue = MPQueue(maxsize=QUEUE_CAPACITY)

# Lock for concurrency control
queue_lock = Lock()

# Global reference to the SQLAlchemy engine
db_engine = None


def load_config():
    with open(CONFIG_FILE, "r") as file:
        return yaml.safe_load(file)


def validate_params(schema, params):
    v = Validator(schema)
    if not v.validate(params):
        raise HTTPException(status_code=422, detail=v.errors)


class KedroRunRequest(BaseModel):
    project: str
    params: dict


@app.on_event("startup")
def setup_db():
    global db_engine
    if DEFAULT_DB_PATH:
        db_engine = create_engine(f"sqlite:///{DEFAULT_DB_PATH}")
    if db_engine:
        metadata = MetaData()
        requests_table = Table(
            "requests",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("project", String),
            Column("params", String),
            Column("received_at", String),
            Column("started_at", String),
            Column("finished_at", String),
            Column("status", String),
            Column("sender_ip", String),
        )
        metadata.create_all(db_engine)


def record_request_in_db(project, params, status, sender_ip):
    conn = db_engine.connect()
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    result = conn.execute(
        "INSERT INTO requests (project, params, received_at, status, sender_ip) VALUES (?, ?, ?, ?, ?)",
        (project, str(params), current_time, status, sender_ip),
    )
    request_id = result.lastrowid
    conn.close()
    return request_id


def update_request_in_db(request_id, status, time_field):
    conn = db_engine.connect()
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        f"UPDATE requests SET {time_field} = ?, status = ? WHERE id = ?",
        (current_time, status, request_id),
    )
    conn.close()


def run_kedro_project(request: KedroRunRequest, sender_ip: str):
    config = load_config()

    # Get project configuration
    project_config = config.get(request.project)
    if not project_config:
        raise HTTPException(
            status_code=404, detail="Project not found in the configuration"
        )

    # Validate the params against the schema defined in the config
    schema = project_config.get("schema", {})
    validate_params(schema, request.params)

    # Clone or pull the project repository using Git CLI
    project_url = project_config["url"]
    project_dir = os.path.join("/tmp", request.project)

    if not os.path.exists(project_dir):
        subprocess.run(["git", "clone", project_url, project_dir], check=True)
    else:
        subprocess.run(["git", "-C", project_dir, "pull"], check=True)

    # Construct the command to run Kedro with the specified parameters
    params_str = ",".join([f"{k}={v}" for k, v in request.params.items()])
    command = f'kedro run --params="{params_str}"'

    # Record the request in the database
    request_id = None
    if db_engine:
        request_id = record_request_in_db(
            request.project, request.params, "queued", sender_ip
        )

    # Run the command in the project directory
    if request_id:
        update_request_in_db(request_id, "running", "started_at")

    result = subprocess.run(
        command, shell=True, cwd=project_dir, capture_output=True, text=True
    )

    if request_id:
        update_request_in_db(request_id, "finished", "finished_at")

    # Return the output or an error message
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr)

    return {"output": result.stdout}


def worker():
    while True:
        task = request_queue.get()
        try:
            run_kedro_project(task["request"], task["sender_ip"])
        except Exception as e:
            print(f"Error executing task: {e}")
        request_queue.task_done()


@app.on_event("startup")
def start_workers():
    for _ in range(NUM_SERVERS):
        process = Process(target=worker)
        process.daemon = True
        process.start()


@app.post("/run_kedro")
def add_to_queue(
    request: KedroRunRequest, background_tasks: BackgroundTasks, client_request: Request
):
    sender_ip = client_request.client.host
    with queue_lock:
        try:
            request_queue.put({"request": request, "sender_ip": sender_ip}, timeout=1)
            background_tasks.add_task(run_kedro_project, request, sender_ip)
        except Full:
            raise HTTPException(status_code=429, detail="Request queue is full")
    return {"status": "added to queue"}
