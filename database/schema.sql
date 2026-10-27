-- ==========================================
-- Smart Attendance Analysis and Shortage Prediction System
-- Database Name
-- ==========================================

CREATE DATABASE IF NOT EXISTS smart_attendance_db;

USE smart_attendance_db;

-- ==========================================
-- Department Table
-- ==========================================

CREATE TABLE departments (

    department_id INT AUTO_INCREMENT PRIMARY KEY,

    department_name VARCHAR(100) NOT NULL UNIQUE

);

-- ==========================================
-- Student Table
-- ==========================================

CREATE TABLE students (

    student_id INT AUTO_INCREMENT PRIMARY KEY,

    register_number VARCHAR(30) UNIQUE NOT NULL,

    full_name VARCHAR(100) NOT NULL,

    email VARCHAR(100) UNIQUE NOT NULL,

    phone VARCHAR(15),

    program VARCHAR(50) NOT NULL,

    department_id INT,

    semester INT NOT NULL,

    academic_year VARCHAR(20) NOT NULL,

    section VARCHAR(10),

    username VARCHAR(50) UNIQUE NOT NULL,

    password VARCHAR(255) NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (department_id)
    REFERENCES departments(department_id)

);

-- ==========================================
-- Faculty Table
-- ==========================================

CREATE TABLE faculty (

    faculty_id INT AUTO_INCREMENT PRIMARY KEY,

    faculty_name VARCHAR(100) NOT NULL,

    email VARCHAR(100) UNIQUE,

    phone VARCHAR(15),

    department_id INT,

    username VARCHAR(50) UNIQUE NOT NULL,

    password VARCHAR(255) NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (department_id)
    REFERENCES departments(department_id)

);

-- ==========================================
-- Admin Table
-- ==========================================

CREATE TABLE admin (

    admin_id INT AUTO_INCREMENT PRIMARY KEY,

    full_name VARCHAR(100),

    username VARCHAR(50) UNIQUE NOT NULL,

    password VARCHAR(255) NOT NULL

);

-- ==========================================
-- Subject Table
-- ==========================================

CREATE TABLE subjects (

    subject_id INT AUTO_INCREMENT PRIMARY KEY,

    subject_code VARCHAR(20) UNIQUE,

    subject_name VARCHAR(100),

    semester INT,

    department_id INT,

    faculty_id INT,

    FOREIGN KEY (department_id)
    REFERENCES departments(department_id),

    FOREIGN KEY (faculty_id)
    REFERENCES faculty(faculty_id)

);

-- ==========================================
-- Attendance Table
-- ==========================================

CREATE TABLE attendance (

    attendance_id INT AUTO_INCREMENT PRIMARY KEY,

    student_id INT,

    subject_id INT,

    attendance_date DATE,

    status ENUM('Present','Absent') NOT NULL,

    marked_by INT,

    FOREIGN KEY (student_id)
    REFERENCES students(student_id),

    FOREIGN KEY (subject_id)
    REFERENCES subjects(subject_id),

    FOREIGN KEY (marked_by)
    REFERENCES faculty(faculty_id)

);

-- ==========================================
-- Notification Table
-- ==========================================

CREATE TABLE notifications (

    notification_id INT AUTO_INCREMENT PRIMARY KEY,

    student_id INT,

    title VARCHAR(200),

    message TEXT,

    status ENUM('Unread','Read') DEFAULT 'Unread',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (student_id)
    REFERENCES students(student_id)

);

-- ==========================================
-- AI Recommendation Table
-- ==========================================

CREATE TABLE ai_recommendations (

    recommendation_id INT AUTO_INCREMENT PRIMARY KEY,

    student_id INT,

    recommendation TEXT,

    generated_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (student_id)
    REFERENCES students(student_id)

);

-- ==========================================
-- Attendance Prediction History
-- ==========================================

CREATE TABLE prediction_history (

    prediction_id INT AUTO_INCREMENT PRIMARY KEY,

    student_id INT,

    current_percentage DECIMAL(5,2),

    predicted_percentage DECIMAL(5,2),

    risk_level VARCHAR(20),

    prediction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (student_id)
    REFERENCES students(student_id)

);

-- ==========================================
-- Insert Default Departments
-- ==========================================

INSERT INTO departments(department_name)
VALUES

('MCA'),

('MBA'),

('BCA'),

('B.Sc Computer Science');

-- ==========================================
-- Default Admin Login
-- ==========================================

INSERT INTO admin(full_name,username,password)

VALUES

('Administrator','admin','admin123');