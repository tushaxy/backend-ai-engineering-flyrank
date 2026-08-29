CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    done BOOLEAN NOT NULL DEFAULT FALSE
);

INSERT INTO tasks (title, done) 
SELECT 'Setup Docker container stack', TRUE
WHERE NOT EXISTS (SELECT 1 FROM tasks);

INSERT INTO tasks (title, done) 
SELECT 'Connect FastAPI to PostgreSQL database', FALSE
WHERE NOT EXISTS (SELECT 1 FROM tasks);

INSERT INTO tasks (title, done) 
SELECT 'Verify volume persistence across restarts', FALSE
WHERE NOT EXISTS (SELECT 1 FROM tasks);
