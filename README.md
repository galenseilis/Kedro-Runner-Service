# Kedro-Runner-Service
A tool to use requests to run Kedro projects.

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
