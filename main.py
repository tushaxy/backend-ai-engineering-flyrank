from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(
    title="Task API",
    version="1.0",
    description="Full CRUD To-Do List API built for FlyRank Backend Track BE-01"
)

# Pydantic Schemas for Request Validation
class TaskCreate(BaseModel):
    title: str

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None

class TaskResponse(BaseModel):
    id: int
    title: str
    done: bool

# In-Memory Task Storage (Pre-filled with 3 tasks)
tasks_db: List[dict] = [
    {"id": 1, "title": "Setup Python environment", "done": True},
    {"id": 2, "title": "Build FastAPI endpoints", "done": False},
    {"id": 3, "title": "Verify Swagger UI at /docs", "done": False}
]

@app.get("/", summary="Root API Info")
def get_root():
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}

@app.get("/health", summary="API Health Check")
def get_health():
    return {"status": "ok"}

@app.get("/tasks", response_model=List[TaskResponse], summary="List all tasks")
def list_tasks():
    return tasks_db

@app.get("/tasks/{id}", response_model=TaskResponse, summary="Get single task")
def get_task(id: int):
    task = next((t for t in tasks_db if t["id"] == id), None)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {id} not found"
        )
    return task

@app.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, summary="Create new task")
def create_task(payload: TaskCreate):
    if not payload.title or not payload.title.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task title cannot be empty"
        )
    next_id = max([t["id"] for t in tasks_db], default=0) + 1
    new_task = {"id": next_id, "title": payload.title.strip(), "done": False}
    tasks_db.append(new_task)
    return new_task

@app.put("/tasks/{id}", response_model=TaskResponse, summary="Update existing task")
def update_task(id: int, payload: TaskUpdate):
    task = next((t for t in tasks_db if t["id"] == id), None)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {id} not found"
        )
    if payload.title is not None:
        if not payload.title.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task title cannot be empty"
            )
        task["title"] = payload.title.strip()
    if payload.done is not None:
        task["done"] = payload.done
    return task

@app.delete("/tasks/{id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete task")
def delete_task(id: int):
    global tasks_db
    task = next((t for t in tasks_db if t["id"] == id), None)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {id} not found"
        )
    tasks_db = [t for t in tasks_db if t["id"] != id]
    return None
