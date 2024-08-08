# Kedro-Runner-Service
A tool to use requests to run Kedro projects.

# Running the FastAPI Server

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

# Sending Requests

```bash
curl -X POST "http://localhost:8000/run_kedro" \
    -H "Content-Type: application/json" \
    -d '{
        "project": "project_1",
        "params": {
            "param1": "option1",
            "param2": 5
        }
    }'
```
