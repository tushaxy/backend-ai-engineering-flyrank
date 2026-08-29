from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
import sqlite3

app = FastAPI(
    title="Task API with SQLite Persistence",
    version="2.0",
    description="Full CRUD To-Do List API backed by SQLite database for FlyRank BE-02"
)

DB_FILE = "tasks.db"

# Database Connection Helper
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# Stage 0: Initialize Database & Seed Tasks
def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            done BOOLEAN NOT NULL DEFAULT 0
        )
    """)
    cursor.execute("SELECT COUNT(*) FROM tasks")
    count = cursor.fetchone()[0]
    if count == 0:
        cursor.executemany("""
            INSERT INTO tasks (title, done) VALUES (?, ?)
        """, [
            ("Setup SQLite database", 1),
            ("Migrate in-memory endpoints to SQL", 0),
            ("Verify persistence after server restart", 0)
        ])
        conn.commit()
    conn.close()

@app.on_event("startup")
def startup_event():
    init_db()

# Pydantic Schemas
class TaskCreate(BaseModel):
    title: str

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None

class TaskResponse(BaseModel):
    id: int
    title: str
    done: bool

# Endpoints
@app.get("/", summary="Root API Info")
def get_root():
    return {"name": "Task API (SQLite)", "version": "2.0", "endpoints": ["/tasks"]}

@app.get("/health", summary="API Health Check")
def get_health():
    return {"status": "ok"}

@app.get("/tasks", response_model=List[TaskResponse], summary="List all tasks from SQLite")
def list_tasks():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, done FROM tasks")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/tasks/{id}", response_model=TaskResponse, summary="Get single task")
def get_task(id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, done FROM tasks WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {id} not found"
        )
    return dict(row)

@app.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, summary="Create task in SQLite")
def create_task(payload: TaskCreate):
    if not payload.title or not payload.title.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task title cannot be empty"
        )
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tasks (title, done) VALUES (?, ?)", (payload.title.strip(), False))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return {"id": new_id, "title": payload.title.strip(), "done": False}

@app.put("/tasks/{id}", response_model=TaskResponse, summary="Update task in SQLite")
def update_task(id: int, payload: TaskUpdate):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, done FROM tasks WHERE id = ?", (id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {id} not found"
        )
    
    current_title = row["title"]
    current_done = row["done"]

    if payload.title is not None:
        if not payload.title.strip():
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task title cannot be empty"
            )
        current_title = payload.title.strip()

    if payload.done is not None:
        current_done = payload.done

    cursor.execute("UPDATE tasks SET title = ?, done = ? WHERE id = ?", (current_title, current_done, id))
    conn.commit()
    conn.close()
    return {"id": id, "title": current_title, "done": current_done}

@app.delete("/tasks/{id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete task from SQLite")
def delete_task(id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM tasks WHERE id = ?", (id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {id} not found"
        )
    cursor.execute("DELETE FROM tasks WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return None
