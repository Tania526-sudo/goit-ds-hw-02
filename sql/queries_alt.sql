PRAGMA foreign_keys = ON;

-- 1) All user tasks (via v_tasks_full + :uid parameter)
SELECT * FROM v_tasks_full WHERE user_id = :uid;

-- 2) Tasks with status 'new' (CTE + JOIN)
WITH s AS (SELECT id FROM status WHERE name = 'new')
SELECT t.*
FROM tasks t
JOIN s ON s.id = t.status_id;

-- 3) Update task status (id=:task_id) to 'in progress'
UPDATE tasks
SET status_id = (SELECT id FROM status WHERE name='in progress')
WHERE id = :task_id;

-- 4) Users without tasks (NOT EXISTS)
SELECT u.*
FROM users u
WHERE NOT EXISTS (
  SELECT 1 FROM tasks t WHERE t.user_id = u.id
);

SELECT u.*
FROM users u
WHERE u.id NOT IN (SELECT DISTINCT user_id FROM tasks);

-- 5) Add a new task to a user :uid (status 'new')
INSERT INTO tasks(title, description, status_id, user_id)
SELECT :title, :description, s.id, :uid
FROM status s
WHERE s.name = 'new';

-- 6) Tasks that are not yet completed (via JOIN and <>)
SELECT t.*
FROM tasks t
JOIN status s ON s.id = t.status_id
WHERE s.name <> 'completed';

-- 7) Delete a specific task (id=:task_id)
DELETE FROM tasks WHERE id = :task_id;

-- 8) Users by email LIKE (e.g.: '%@example.com' or '%john%')
SELECT * FROM users WHERE email LIKE :pattern;

-- 9) Update user fullname
UPDATE users SET fullname = :new_name WHERE id = :uid;

-- 10) Number of tasks by status (via LEFT JOIN; order by number)
SELECT s.name AS status, COUNT(t.id) AS task_count
FROM status s
LEFT JOIN tasks t ON t.status_id = s.id
GROUP BY s.id, s.name
ORDER BY task_count DESC;

-- 11) Tasks assigned to users with a specific domain (JOIN + LIKE)
SELECT t.*
FROM tasks t
JOIN users u ON u.id = t.user_id
WHERE u.email LIKE :domain_pattern;

-- 12) Tasks without description (NULL or empty/whitespace)
SELECT *
FROM tasks
WHERE description IS NULL OR TRIM(description) = '';

-- 13) Users and their tasks in status 'in progress'
SELECT u.fullname, u.email, t.id AS task_id, t.title
FROM users u
JOIN tasks t  ON t.user_id = u.id
JOIN status s ON s.id = t.status_id
WHERE s.name = 'in progress'
ORDER BY u.fullname, t.id;

-- 14) Users + their task count (LEFT JOIN + GROUP BY)
SELECT u.id, u.fullname, u.email, COUNT(t.id) AS tasks_count
FROM users u
LEFT JOIN tasks t ON t.user_id = u.id
GROUP BY u.id, u.fullname, u.email
ORDER BY tasks_count DESC, u.fullname;