-- SQL script to create class_students_two mapping table
CREATE TABLE IF NOT EXISTS class_students_two (
    id INT AUTO_INCREMENT PRIMARY KEY,
    class_id INT NOT NULL,
    student_id INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_class_student (class_id, student_id),
    FOREIGN KEY (class_id) REFERENCES classes_two(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
);