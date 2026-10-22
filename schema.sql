DROP TABLE IF EXISTS reminder;
DROP TABLE IF EXISTS item_requirement;
DROP TABLE IF EXISTS personal_item;
DROP TABLE IF EXISTS task;
DROP TABLE IF EXISTS class_session;
DROP TABLE IF EXISTS course;
DROP TABLE IF EXISTS sim_state;
DROP TABLE IF EXISTS student;

CREATE TABLE student (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  alexa_user_id TEXT UNIQUE,
  avatar TEXT DEFAULT '🎓'
);

CREATE TABLE course (
  id INTEGER PRIMARY KEY,
  student_id INTEGER NOT NULL,
  code TEXT,
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('THEORY','LAB')),
  FOREIGN KEY (student_id) REFERENCES student(id)
);

CREATE TABLE class_session (
  id INTEGER PRIMARY KEY,
  course_id INTEGER NOT NULL,
  day_of_week TEXT NOT NULL,          -- MONDAY, TUESDAY ...
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL,             -- 'HH:MM'
  room TEXT,
  FOREIGN KEY (course_id) REFERENCES course(id)
);

CREATE TABLE task (
  id INTEGER PRIMARY KEY,
  student_id INTEGER NOT NULL,
  course_id INTEGER,
  title TEXT NOT NULL,
  subject_name TEXT,
  due_at TEXT NOT NULL,               -- ISO 'YYYY-MM-DDTHH:MM:SS'
  status TEXT DEFAULT 'TODO' CHECK (status IN ('TODO', 'IN_PROGRESS', 'COMPLETED')),
  weight INTEGER DEFAULT 3,           -- 1..5 priority
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (student_id) REFERENCES student(id),
  FOREIGN KEY (course_id) REFERENCES course(id)
);

CREATE TABLE personal_item (
  id INTEGER PRIMARY KEY,
  student_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  always_carry INTEGER DEFAULT 0,
  FOREIGN KEY (student_id) REFERENCES student(id)
);

CREATE TABLE item_requirement (
  id INTEGER PRIMARY KEY,
  item_id INTEGER NOT NULL,
  session_type TEXT,
  note TEXT,
  FOREIGN KEY (item_id) REFERENCES personal_item(id)
);

CREATE TABLE reminder (
  id INTEGER PRIMARY KEY,
  student_id INTEGER NOT NULL,
  task_id INTEGER,
  text TEXT NOT NULL,
  remind_date TEXT,                   -- 'YYYY-MM-DD'
  remind_time TEXT,                   -- 'HH:MM'
  status TEXT DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'SENT', 'DISMISSED')),
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (student_id) REFERENCES student(id),
  FOREIGN KEY (task_id) REFERENCES task(id) ON DELETE CASCADE
);

CREATE TABLE sim_state (
  student_id INTEGER PRIMARY KEY,
  sim_now TEXT NOT NULL,
  location TEXT NOT NULL,
  destination TEXT,
  is_live INTEGER DEFAULT 1,
  FOREIGN KEY (student_id) REFERENCES student(id)
);

-- ==========================================
-- Demo Data: Multi-Student Isolated Profiles
-- ==========================================

-- Student 1: Ravi Kumar (Default Alexa linked user)
INSERT INTO student (id, name, email, alexa_user_id, avatar) VALUES
 (1, 'Ravi Kumar', 'ravi@campus.edu', 'amzn1.ask.account.RAVI_123', '👨‍💻'),
 (2, 'Priya Sharma', 'priya@campus.edu', 'amzn1.ask.account.PRIYA_456', '👩‍🔬');

-- Ravi's Courses (Student 1)
INSERT INTO course (id, student_id, code, name, type) VALUES
 (1, 1, 'CS301', 'DBMS', 'THEORY'),
 (2, 1, 'CS391', 'DBMS Lab', 'LAB'),
 (3, 1, 'CS305', 'Operating Systems', 'THEORY'),
 (4, 1, 'CS307', 'Computer Networks', 'THEORY');

-- Ravi's Schedule (Monday - Friday)
INSERT INTO class_session (course_id, day_of_week, start_time, end_time, room) VALUES
 (1, 'MONDAY', '09:00', '10:00', 'B-204'),
 (3, 'MONDAY', '11:00', '12:00', 'B-110'),
 (2, 'MONDAY', '14:00', '16:00', 'Lab 3'),
 (4, 'TUESDAY', '10:00', '11:00', 'C-101'),
 (3, 'TUESDAY', '13:00', '14:00', 'B-110'),
 (1, 'TUESDAY', '15:00', '16:00', 'B-204'),
 (4, 'WEDNESDAY', '09:30', '10:30', 'C-101'),
 (1, 'WEDNESDAY', '11:30', '12:30', 'B-204'),
 (2, 'WEDNESDAY', '14:00', '16:00', 'Lab 3'),
 (3, 'THURSDAY', '10:00', '11:00', 'B-110'),
 (4, 'THURSDAY', '11:30', '12:30', 'C-101'),
 (1, 'THURSDAY', '14:00', '15:00', 'B-204'),
 (1, 'FRIDAY', '09:00', '10:00', 'B-204'),
 (3, 'FRIDAY', '10:30', '11:30', 'B-110'),
 (4, 'FRIDAY', '14:00', '15:00', 'C-101');

-- Ravi's Initial Tasks & Assignments
INSERT INTO task (id, student_id, course_id, title, subject_name, due_at, status, weight) VALUES
 (1, 1, 1, 'DBMS Assignment 3 (Normalization)', 'DBMS', '2026-10-17T23:59:00', 'TODO', 5),
 (2, 1, 3, 'OS Memory Management Reading', 'Operating Systems', '2026-10-16T17:00:00', 'TODO', 3);

-- Ravi's Daily Reminders
INSERT INTO reminder (id, student_id, task_id, text, remind_date, remind_time, status) VALUES
 (1, 1, 1, 'Daily Reminder: DBMS assignment is due in 5 days (Oct 17)', '2026-10-12', '08:00', 'PENDING'),
 (2, 1, 2, 'Daily Reminder: OS Reading is due in 4 days (Oct 16)', '2026-10-12', '08:00', 'PENDING');

-- Ravi's Items
INSERT INTO personal_item VALUES
 (1, 1, 'Laptop', 0),
 (2, 1, 'Laptop charger', 0),
 (3, 1, 'College ID card', 1),
 (4, 1, 'Lab Record Book', 0);

INSERT INTO item_requirement (item_id, session_type, note) VALUES
 (1, 'LAB', 'Needed for lab sessions'),
 (2, 'LAB', 'Lab sockets are limited'),
 (4, 'LAB', 'Must submit before lab starts');

INSERT INTO sim_state VALUES (1, '2026-10-20T07:45:00', 'AT_HOME', NULL, 1);


-- Priya's Courses (Student 2 - Isolated Data)
INSERT INTO course (id, student_id, code, name, type) VALUES
 (5, 2, 'AI401', 'Artificial Intelligence', 'THEORY'),
 (6, 2, 'AI491', 'AI & Machine Learning Lab', 'LAB'),
 (7, 2, 'CC405', 'Cloud Computing', 'THEORY');

-- Priya's Schedule (Monday - Friday)
INSERT INTO class_session (course_id, day_of_week, start_time, end_time, room) VALUES
 (5, 'MONDAY', '08:30', '09:30', 'A-301'),
 (6, 'MONDAY', '10:30', '12:30', 'AI-Lab 2'),
 (7, 'MONDAY', '15:00', '16:00', 'A-202'),
 (5, 'TUESDAY', '09:00', '10:00', 'A-301'),
 (7, 'TUESDAY', '11:00', '12:00', 'A-202'),
 (6, 'TUESDAY', '14:00', '15:30', 'AI-Lab 2'),
 (5, 'WEDNESDAY', '10:00', '11:00', 'A-301'),
 (7, 'WEDNESDAY', '13:00', '14:00', 'A-202'),
 (7, 'THURSDAY', '09:00', '10:00', 'A-202'),
 (6, 'THURSDAY', '11:00', '13:00', 'AI-Lab 2'),
 (5, 'FRIDAY', '10:00', '11:00', 'A-301'),
 (7, 'FRIDAY', '14:00', '15:00', 'A-202');

-- Priya's Initial Tasks & Reminders
INSERT INTO task (id, student_id, course_id, title, subject_name, due_at, status, weight) VALUES
 (3, 2, 5, 'AI Neural Network Project Report', 'Artificial Intelligence', '2026-10-25T23:59:00', 'TODO', 4);

INSERT INTO reminder (id, student_id, task_id, text, remind_date, remind_time, status) VALUES
 (3, 2, 3, 'Daily Reminder: AI Neural Network Report is due in 3 days', '2026-10-20', '08:00', 'PENDING');

INSERT INTO personal_item VALUES
 (5, 2, 'MacBook Pro', 0),
 (6, 2, 'College ID badge', 1);

INSERT INTO item_requirement (item_id, session_type, note) VALUES
 (5, 'LAB', 'Python environment required');

INSERT INTO sim_state VALUES (2, '2026-10-20T07:45:00', 'AT_HOME', NULL, 1);
