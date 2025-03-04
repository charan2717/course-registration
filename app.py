from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database Setup
def init_db():
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()

        # Drop the existing table to avoid schema issues (Only do this in development)
        cursor.execute("DROP TABLE IF EXISTS courses")

        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, 
                username TEXT UNIQUE, 
                password TEXT, 
                role TEXT
            )
        ''')

        # Create courses table with slot column
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY, 
                faculty TEXT, 
                course_name TEXT, 
                slot TEXT,
                students TEXT
            )
        ''')

        conn.commit()

# Call init_db() on startup
init_db()

# Home Page
@app.route('/')
def home():
    return render_template('index.html')

# Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        hashed_password = generate_password_hash(password)

        try:
            with sqlite3.connect("database.db") as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                               (username, hashed_password, role))
                conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return "Username already exists! Choose a different one."

    return render_template('register.html')

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        with sqlite3.connect("database.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username=? AND role=?", (username, role))
            user = cursor.fetchone()

        if user and check_password_hash(user[2], password):
            session['username'] = username
            session['role'] = role
            if role == 'student':
                return redirect(url_for('student_dashboard'))
            else:
                return redirect(url_for('faculty_dashboard'))
        else:
            return "Invalid credentials!"

    return render_template('login.html')

@app.route('/faculty', methods=['GET', 'POST'])
def faculty_dashboard():
    if 'username' in session and session['role'] == 'faculty':
        faculty = session['username']

        if request.method == 'POST':
            course_name = request.form['course_name']
            time_slot = request.form['time_slot']  # New field for slot

            with sqlite3.connect("database.db") as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO courses (faculty, course_name, slot, students) VALUES (?, ?, ?, ?)", 
                               (faculty, course_name, time_slot, ""))
                conn.commit()

        with sqlite3.connect("database.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, course_name, slot, students FROM courses WHERE faculty=?", (faculty,))
            courses = cursor.fetchall()

        # Convert student list to a better format
        formatted_courses = []
        for course in courses:
            course_id, course_name, slot, students = course
            student_list = students.split(",") if students else []
            formatted_courses.append((course_id, course_name, slot, student_list))

        return render_template('faculty_dashboard.html', courses=formatted_courses)

    return redirect(url_for('login'))


# Student Dashboard
@app.route('/student', methods=['GET', 'POST'])
def student_dashboard():
    if 'username' in session and session['role'] == 'student':
        student = session['username']
        selected_subject = None
        faculty_list = []

        with sqlite3.connect("database.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT course_name FROM courses")
            subjects = [row[0] for row in cursor.fetchall()]

            # Step 1: Show faculty after selecting a subject
            if request.method == 'POST' and 'subject' in request.form:
                selected_subject = request.form['subject']
                cursor.execute("SELECT id, faculty, course_name, slot FROM courses WHERE course_name=?", 
                               (selected_subject,))
                faculty_list = cursor.fetchall()

            # Step 2: Register for the selected course
            if request.method == 'POST' and 'course_id' in request.form:
                course_id = request.form['course_id']
                cursor.execute("SELECT students FROM courses WHERE id=?", (course_id,))
                row = cursor.fetchone()
                current_students = row[0] if row and row[0] else ""

                # Check if student is already registered
                if student not in current_students.split(","):
                    updated_students = f"{current_students},{student}" if current_students else student
                    cursor.execute("UPDATE courses SET students=? WHERE id=?", (updated_students, course_id))
                    conn.commit()

        # Step 3: Fetch registered courses
        registered_courses = []
        with sqlite3.connect("database.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, faculty, course_name, slot, students FROM courses")
            for course in cursor.fetchall():
                if course[4]:  # Ensure students column is not empty
                    if student in course[4].split(","):  # Check if student is registered
                        registered_courses.append(course)

        return render_template('student_dashboard.html', subjects=subjects, selected_subject=selected_subject,
                               faculty_list=faculty_list, registered_courses=registered_courses)

    return redirect(url_for('login'))

@app.route('/faculty/view_students/<int:course_id>')
def view_students(course_id):
    if 'username' in session and session['role'] == 'faculty':
        with sqlite3.connect("database.db") as conn:
            cursor = conn.cursor()

            # Fetch student registrations for this course
            cursor.execute('''SELECT student_name, reg_no, email FROM registrations WHERE course_id=?''', (course_id,))
            students = cursor.fetchall()

            # Debugging output
            print("Course ID:", course_id)
            print("Fetched students:", students)

        return render_template('view_students.html', students=students)

    return redirect(url_for('login'))


@app.route('/register_course/<int:course_id>', methods=['POST'])
def register_course(course_id):
    if 'username' in session and session['role'] == 'student':
        student_username = session['username']
        
        with sqlite3.connect("database.db") as conn:
            cursor = conn.cursor()

            # Fetch student details
            cursor.execute('''SELECT username, name, reg_no, email FROM users WHERE username=?''', (student_username,))
            student = cursor.fetchone()
            
            if student:
                student_name, reg_no, email = student[1], student[2], student[3]

                # Debugging output
                print(f"Registering {student_name} (Reg No: {reg_no}) for Course ID: {course_id}")

                cursor.execute('''INSERT INTO registrations (student_username, student_name, reg_no, email, course_id) 
                                  VALUES (?, ?, ?, ?, ?)''',
                               (student_username, student_name, reg_no, email, course_id))
                conn.commit()

    return redirect(url_for('student_dashboard'))




# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
