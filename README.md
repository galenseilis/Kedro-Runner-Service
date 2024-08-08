# Kedro-Runner-Service
A tool to use requests to run Kedro projects.

# Example Project Config

```yaml
project_1:
  url: "https://github.com/your-repo/project_1.git"
  schema:
    param1:
      type: "string"
      allowed: ["option1", "option2"]
    param2:
      type: "integer"
      min: 0
      max: 10

project_2:
  url: "https://github.com/your-repo/project_2.git"
  schema:
    key1:
      type: "string"
    key2:
      type: "float"
      min: 0.0
      max: 100.0
```

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
