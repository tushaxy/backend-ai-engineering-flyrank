import os
import time
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(
    title="Task API with Containerized PostgreSQL",
    version="4.0",
    description="Full CRUD API backed by PostgreSQL running in Docker for FlyRank BE-04"
)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/tasks_db")

def get_db():
    retries = 5
    while retries > 0:
        try:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
            return conn
        except psycopg2.OperationalError:
            retries -= 1
            time.sleep(2)
    raise Exception("Could not connect to PostgreSQL database.")

class TaskCreate(BaseModel):
    title: str

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None

class TaskResponse(BaseModel):
    id: int
    title: str
    done: bool

@app.get("/", summary="Root API Info")
def get_root():
    return {"name": "Task API (PostgreSQL Docker)", "version": "4.0", "endpoints": ["/tasks"]}

@app.get("/health", summary="API Health Check")
def get_health():
    return {"status": "ok"}

@app.get("/tasks", response_model=List[TaskResponse], summary="List all tasks")
def list_tasks():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, done FROM tasks ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/tasks/{id}", response_model=TaskResponse, summary="Get single task")
def get_task(id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, done FROM tasks WHERE id = %s", (id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {id} not found")
    return dict(row)

@app.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, summary="Create task")
def create_task(payload: TaskCreate):
    if not payload.title or not payload.title.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task title cannot be empty")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tasks (title, done) VALUES (%s, %s) RETURNING id, title, done", (payload.title.strip(), False))
    new_task = cursor.fetchone()
    conn.commit()
    conn.close()
    return dict(new_task)

@app.put("/tasks/{id}", response_model=TaskResponse, summary="Update task")
def update_task(id: int, payload: TaskUpdate):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, done FROM tasks WHERE id = %s", (id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {id} not found")
    
    current_title = row["title"]
    current_done = row["done"]

    if payload.title is not None:
        if not payload.title.strip():
            conn.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task title cannot be empty")
        current_title = payload.title.strip()

    if payload.done is not None:
        current_done = payload.done

    cursor.execute("UPDATE tasks SET title = %s, done = %s WHERE id = %s RETURNING id, title, done", (current_title, current_done, id))
    updated_task = cursor.fetchone()
    conn.commit()
    conn.close()
    return dict(updated_task)

@app.delete("/tasks/{id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete task")
def delete_task(id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM tasks WHERE id = %s", (id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {id} not found")
    cursor.execute("DELETE FROM tasks WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    return None
