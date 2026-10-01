# Track C: Schemas and API

## What is a Schema & API Skeleton?
A schema is a strict data contract that defines exactly what a module accepts and returns. An API (Application Programming Interface) exposes this contract to the outside world, usually over HTTP. We use Pydantic to enforce the schema and FastAPI to serve it.

## Why do we need it here?
Our frontend teammate is building the dashboard right now. They can't wait 10 days for us to finish our routing logic. By defining `AnalysisResult` in Pydantic and mocking the output JSON, they can build the entire UI immediately. The FastAPI skeleton gives them the exact endpoint they will eventually call.

## Example
```python
from pydantic import BaseModel
from fastapi import FastAPI

class Result(BaseModel):
    flood_area: float

app = FastAPI()
@app.post("/analyze", response_model=Result)
def run_analysis():
    return Result(flood_area=12.5)
```

## Quiz
1. **Why not just return a Python dictionary from our module?**
2. **What happens if our code produces `n_bridges = "five"` but the schema says `int`?**
3. **Why do we need a `/health` endpoint?**

<details>
<summary>Answers</summary>

1. A dictionary has no guarantees. Pydantic ensures every required field exists and has the correct type, catching bugs early.
2. Pydantic will raise a validation error before the data is sent to the frontend, protecting the client from crashing.
3. For infrastructure (like Kubernetes or Docker) to automatically check if our API is running and restart it if it crashes.
</details>
