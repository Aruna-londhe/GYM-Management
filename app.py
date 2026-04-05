from flask import Flask, render_template_string, request, redirect, session, g, url_for
import sqlite3
from datetime import datetime, timedelta
import re
import qrcode
from io import BytesIO
from flask import send_file

app = Flask(__name__)
app.secret_key = "trends_gym_enterprise_ultra_secure_key_2026"

DATABASE = "gym.db"

BG_IMAGE = "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?q=80&w=2070"

def get_db():
    if "_database" not in g:
        g._database = sqlite3.connect(DATABASE)
        g._database.row_factory = sqlite3.Row
    return g._database

@app.teardown_appcontext
def close_db(error):
    db = g.pop("_database", None)
    if db:
        db.close()

def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT,
            age INTEGER,
            weight REAL,
            before_weight REAL,
            after_weight REAL,
            plan TEXT,
            coach TEXT,
            workout_type TEXT
   )  
      """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS user(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            mobile TEXT NOT NULL,
            gender TEXT,
            is_admin INTEGER DEFAULT 0,
            admin_status TEXT DEFAULT 'approved',
            join_date TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS subscription(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            plan_name TEXT,
            amount INTEGER,
            start_date TEXT,
            end_date TEXT,
            status TEXT DEFAULT 'active',
            FOREIGN KEY(user_id) REFERENCES user(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS machines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine TEXT NOT NULL,
            slot TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            booking_time TEXT,
            UNIQUE(machine, slot, date),
            FOREIGN KEY(user_id) REFERENCES user(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS attendance(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            UNIQUE(user_id, date),
            FOREIGN KEY(user_id) REFERENCES user(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS plan_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan TEXT NOT NULL,
            request_date TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY(user_id) REFERENCES user(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            plan TEXT,
            date TEXT
        )
    """)
    admin_exists = db.execute("SELECT * FROM user WHERE username='admin'").fetchone()
    if not admin_exists:
        db.execute("""
            INSERT INTO user(name, username, password, mobile, gender, is_admin, admin_status, join_date) 
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """, ("System Admin", "admin", "admin", "0000000000", "Other", 1, "approved", str(datetime.now().date())))
    db.commit()


    

GLOBAL_LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trend's Gym | {{ title }}</title>
    <script src="https://unpkg.com/lucide@latest"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --secondary: #64748b;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --dark: #0f172a;
            --light: #f8fafc;
            --glass: rgba(255, 255, 255, 0.95);
        }
        * { box-sizing: border-box; transition: all 0.2s ease; }
        body {
            margin: 0;
            font-family: 'Inter', sans-serif;
            background: url('{{ bg_url }}') no-repeat center center fixed;
            background-size: cover;
            min-height: 100vh;
            display: flex;
        }
        .main-overlay {
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(15, 23, 42, 0.75);
            z-index: 0;
        }
        .sidebar {
            width: 280px;
            background: rgba(15, 23, 42, 0.9);
            backdrop-filter: blur(10px);
            border-right: 1px solid rgba(255,255,255,0.1);
            height: 100vh;
            position: sticky;
            top: 0;
            display: flex;
            flex-direction: column;
            padding: 30px 20px;
            z-index: 100;
            color: white;
        }
        .sidebar h2 {
            font-size: 22px;
            color: var(--primary);
            margin-bottom: 40px;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .nav-item {
            text-decoration: none;
            color: #94a3b8;
            padding: 14px 18px;
            border-radius: 12px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 12px;
            font-weight: 500;
        }
        .nav-item:hover {
            background: rgba(255,255,255,0.05);
            color: white;
        }
        .nav-item.active {
            background: var(--primary);
            color: white;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
        }
        .content-wrapper {
            flex: 1;
            position: relative;
            z-index: 10;
            padding: 40px;
            overflow-y: auto;
        }
        .glass-card {
            background: var(--glass);
            border-radius: 24px;
            padding: 40px;
            box-shadow: 0 20px 25px -5px rgba(0,0,0,0.3);
            max-width: 1000px;
            margin: 0 auto;
        }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; font-weight: 600; font-size: 14px; color: var(--dark); }
        input, select, textarea {
            width: 100%;
            padding: 14px;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            background: #f8fafc;
            font-size: 15px;
            outline: none;
        }
        input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(37,99,235,0.1); }
        button {
            padding: 14px 24px;
            border-radius: 12px;
            border: none;
            font-weight: 700;
            cursor: pointer;
            font-size: 15px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        .btn-primary { background: var(--primary); color: white; width: 100%; }
        .btn-primary:hover { background: var(--primary-hover); transform: translateY(-1px); }
        .btn-danger { background: var(--danger); color: white; }
        .btn-danger:hover { opacity: 0.9; }
        .table-container { overflow-x: auto; margin-top: 25px; }
        table { width: 100%; border-collapse: collapse; }
        th { background: #f1f5f9; padding: 15px; text-align: left; font-size: 12px; text-transform: uppercase; color: var(--secondary); }
        td { padding: 15px; border-bottom: 1px solid #f1f5f9; font-size: 14px; color: var(--dark); }
        .badge {
            padding: 6px 12px;
            border-radius: 99px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
        }
        .badge-success { background: #dcfce7; color: #166534; }
        .badge-warning { background: #fef3c7; color: #92400e; }
        .badge-danger { background: #fee2e2; color: #991b1b; }
        .alert {
            padding: 16px;
            border-radius: 12px;
            margin-bottom: 25px;
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 14px;
        }
        .alert-error { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
        .alert-success { background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
        .portal-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-top: 30px;
        }
        .portal-item {
            background: white;
            padding: 30px;
            border-radius: 20px;
            text-decoration: none;
            color: var(--dark);
            border: 1px solid #e2e8f0;
            text-align: center;
        }
        .portal-item:hover { border-color: var(--primary); transform: translateY(-5px); }
        .portal-item i { font-size: 32px; color: var(--primary); margin-bottom: 15px; }
        @media (max-width: 768px) {
            body { flex-direction: column; }
            .sidebar { width: 100%; height: auto; position: relative; }
            .portal-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="main-overlay"></div>
    {% if session.get('username') or session.get('is_guest') %}
    <div class="sidebar">
        <h2><i data-lucide="dumbbell"></i> TREND'S GYM</h2>
        <a href="/dashboard" class="nav-item {{ 'active' if active_page == 'dashboard' }}">
            <i data-lucide="layout-dashboard"></i> Dashboard
        </a>
        {% if session.get('is_admin') %}
            <a href="/admin_panel" class="nav-item {{ 'active' if active_page == 'admin' }}">
                <i data-lucide="shield-check"></i> Admin Panel
            </a>
            <a href="/admin_reports" class="nav-item {{ 'active' if active_page == 'reports' }}">
                <i data-lucide="bar-chart-3"></i> Reports
            </a>
        {% else %}
            <a href="/mark_attendance" class="nav-item {{ 'active' if active_page == 'attendance' }}">
                <i data-lucide="calendar-check"></i> Attendance
            </a>
            <a href="/membership_plans" class="nav-item {{ 'active' if active_page == 'plans' }}">
                <i data-lucide="credit-card"></i> Memberships
            </a>
            <a href="/book_machines" class="nav-item {{ 'active' if active_page == 'machines' }}">
                <i data-lucide="armchair"></i> Gym Machines
            </a>
        {% endif %}
        <div style="margin-top: auto;">
            <hr style="opacity: 0.1; margin-bottom: 20px;">
            <a href="/logout" class="nav-item" style="color: var(--danger);">
                <i data-lucide="log-out"></i> Logout
            </a>
        </div>
    </div>
    {% endif %}
    <div class="content-wrapper">
        <div class="glass-card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:30px;">
                <h1 style="margin:0; font-size:28px; color:var(--dark)">{{ title }}</h1>
                {% if session.get('username') %}
                    <div style="text-align:right">
                        <span style="display:block; font-weight:700; color:var(--primary)">@{{ session['username'] }}</span>
                        <span style="font-size:12px; color:var(--secondary)">{{ "System Administrator" if session.get('is_admin') else "Club Member" }}</span>
                    </div>
                {% endif %}
            </div>
            {{ content|safe }}
        </div>
    </div>
    <script>lucide.createIcons();</script>
</body>
</html>
"""

def validate_signup(name, mobile, password):
    if not re.match(r"^[A-Za-z\s]+$", name):
        return "Full Name must contain only letters and spaces."
    if not re.match(r"^\d{10}$", mobile):
        return "Mobile Number must be exactly 10 digits."
    if len(password) < 6:
        return "Password security error: Minimum 6 characters required."
    return None

def db_cleanup_user(user_id):
    db = get_db()
    db.execute("DELETE FROM attendance WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM machines WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM subscription WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM plan_requests WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM payments WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM user WHERE id=?", (user_id,))
    db.commit()

@app.route("/")
def landing_page():
    bg = "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?q=80&w=2070"
    content = """
    <p style="color:var(--secondary); font-size:18px; line-height:1.6">Welcome to Trend's Gym Management. Our platform provides a seamless experience for tracking your workouts, managing memberships, and booking equipment.</p>
    <div class="portal-grid">
        <a href="/member_login" class="portal-item">
            <i data-lucide="user"></i>
            <h3>Member Login</h3>
            <p>Access your training dashboard and bookings.</p>
        </a>
        <a href="/register" class="portal-item">
            <i data-lucide="user-plus"></i>
            <h3>New Registration</h3>
            <p>Join our fitness community today.</p>
        </a>
        <a href="/guest_mode" class="portal-item">
            <i data-lucide="eye"></i>
            <h3>Guest Mode</h3>
            <p>Explore our facilities and plan schedules.</p>
        </a>
        <a href="/admin_gateway" class="portal-item">
            <i data-lucide="shield-check"></i>
            <h3>Admin Gateway</h3>
            <p>Authorized personnel only access point.</p>
        </a>
    </div>
    """
    return render_template_string(GLOBAL_LAYOUT, title="The Fitness Portal", content=content, bg_url=bg)

@app.route("/guest_mode")
def guest_mode():
    session.clear()
    session['is_guest'] = True
    session['username'] = "Guest_Visitor"
    return redirect(url_for('dashboard'))

@app.route("/member_login", methods=["GET", "POST"])
def member_login():
    bg = "https://images.unsplash.com/photo-1540497077202-7c8a3999166f?q=80&w=2070"
    error = ""

    if request.method == "POST":
        db = get_db()

        username = request.form['username']
        password = request.form['password']

        # 🔍 Check user exists
        user = db.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        ).fetchone()

        # 🚀 AUTO CREATE USER IF NOT EXISTS
        if not user:
            db.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, password)
            )
            db.commit()

            # fetch again
            user = db.execute(
                "SELECT * FROM users WHERE username=?",
                (username,)
            ).fetchone()

        # ✅ LOGIN SUCCESS
        if user:
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = False

            return redirect(url_for('dashboard'))

        else:
            error = "Authentication failed. Invalid username or password."

    content = f"""
    {f'<div class="alert alert-error">{error}</div>' if error else ''}

    <form method="post" style="max-width:400px; margin:0 auto">
        <div class="form-group">
            <label>Username</label>
            <input name="username" placeholder="Enter username" required>
        </div>

        <div class="form-group">
            <label>Password</label>
            <input name="password" type="password" placeholder="Enter password" required>
        </div>

        <button class="btn-primary">Login</button>
    </form>
    """

    return render_template_string(
        GLOBAL_LAYOUT,
        title="Member Login",
        content=content,
        bg_url=bg
    )

@app.route("/admin_gateway", methods=["GET", "POST"])
def admin_gateway():
    bg = "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?q=80&w=2070"
    error = ""
    if request.method == "POST":
        db = get_db()
        user = db.execute("SELECT * FROM user WHERE username=? AND password=? AND is_admin=1", 
                          (request.form['username'], request.form['password'])).fetchone()
        if user:
            if user['admin_status'] == 'pending':
                error = "Access Denied: Your admin credentials are awaiting approval."
            else:
                session.clear()
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['is_admin'] = True
                return redirect(url_for('admin_panel'))
        else:
            error = "Security Violation: Invalid Admin Credentials."
    content = f"""
    <div style="background:rgba(239, 68, 68, 0.05); border:1px dashed var(--danger); padding:20px; border-radius:15px; margin-bottom:25px; text-align:center">
        <p style="color:var(--danger); font-weight:700; margin:0">SECURE ACCESS AREA</p>
    </div>
    {f'<div class="alert alert-error">{error}</div>' if error else ''}
    <form method="post" style="max-width:400px; margin:0 auto">
        <div class="form-group">
            <label>Administrator ID</label>
            <input name="username" placeholder="Admin username" required>
        </div>
        <div class="form-group">
            <label>Security Key</label>
            <input name="password" type="password" placeholder="Password" required>
        </div>
        <button class="btn-primary" style="background:var(--dark)">Authenticate Admin</button>
        <div style="text-align:center; margin-top:20px">
            <a href="/" style="color:var(--secondary); text-decoration:none; font-size:14px">← Exit Secure Zone</a>
        </div>
    </form>
    """
    return render_template_string(GLOBAL_LAYOUT, title="Admin Authentication", content=content, bg_url=bg)

@app.route("/register", methods=["GET", "POST"])
def register():
    bg = "https://images.unsplash.com/photo-1571902943202-507ec2618e8f?q=80&w=2075"
    error = ""
    success = ""

    if request.method == "POST":
        db = get_db()

        name = request.form['name'].strip()
        user = request.form['username'].strip()
        mob = request.form['mobile'].strip()
        gen = request.form.get('gender')
        pw = request.form['password'].strip()
        role = request.form['role']

        age = request.form['age']
        weight = request.form['weight']
        plan = request.form['plan']
        coach = request.form['coach']
        workout = request.form['workout']

        error = validate_signup(name, mob, pw)

        if not error:
            existing = db.execute("SELECT * FROM user WHERE username=?", (user,)).fetchone()

            if existing:
                error = "Username already exists."
            else:
                is_adm = 1 if role == "admin" else 0

                db.execute("""
                INSERT INTO user(
                    name, username, password, mobile, gender,
                    is_admin, admin_status, join_date,
                    age, weight, plan, coach, workout_type
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    name, user, pw, mob, gen,
                    is_adm, 'approved', str(datetime.now().date()),
                    age, weight, plan, coach, workout
                ))

                db.commit()
                success = "Registration successful!"

    content = f"""
    {f'<div class="alert alert-error">{error}</div>' if error else ''}
    {f'<div class="alert alert-success">{success}</div>' if success else ''}

    <form method="post" style="max-width:500px; margin:auto">

        <div class="form-group">
            <label>Name</label>
            <input name="name" required>
        </div>

        <div class="form-group">
            <label>Username</label>
            <input name="username" required>
        </div>

        <div class="form-group">
            <label>Mobile</label>
            <input name="mobile" required>
        </div>

        <div class="form-group">
            <label>Age</label>
            <input type="number" name="age" required>
        </div>

        <div class="form-group">
            <label>Weight (kg)</label>
            <input type="number" name="weight" required>
        </div>

        <div class="form-group">
            <label>Gender</label>
            <select name="gender">
                <option>Male</option>
                <option>Female</option>
                <option>Other</option>
            </select>
        </div>

        <div class="form-group">
            <label>Plan</label>
            <select name="plan">
                <option>15 Days</option>
                <option>3 Months</option>
                <option>1 Year</option>
            </select>
        </div>

        <div class="form-group">
            <label>Coach</label>
            <select name="coach">
                <option>Self</option>
                <option>Ayush Londhe</option>
                <option>Raj Gurav</option>
                <option>Amol Kadam</option>
                <option>Nilesh Shikhe</option>
                <option>Swapnil Balwadkar</option>
                <option>Aruna Londhe</option>
                <option>Pratiksha Rampure</option>
                <option>Arti Pansare</option>
            </select>
        </div>

        <div class="form-group">
            <label>Workout Type</label>
            <select name="workout">
                <option>Cardio</option>
                <option>Strength Training</option>
                <option>Flexibility</option>
                <option>HIIT</option>
                <option>Body Weight</option>
                <option>Group Fitness</option>
                <option>Specialized Training</option>
                <option>Zumba</option>
            </select>
        </div>

        <div class="form-group">
            <label>Password</label>
            <input type="password" name="password" required>
        </div>

        <div class="form-group">
            <label>Role</label>
            <select name="role">
                <option value="member">Member</option>
                <option value="admin">Admin</option>
            </select>
        </div>

        <button class="btn-primary">Register</button>
    </form>

    <div style="text-align:center; margin-top:20px;">
        <p>📲 Share this link with new members:</p>
        <b>http://127.0.0.1:5000/register</b>
    </div>
    """

    return render_template_string(GLOBAL_LAYOUT, title="Register", content=content, bg_url=bg)

@app.route("/dashboard")
def dashboard():
    if not session.get('username'):
        return redirect(url_for('member_login'))

    username = session.get('username')

    db = get_db()

    user = db.execute(
        "SELECT * FROM users WHERE username=?", (username,)
    ).fetchone()

    if not user:
        return "<h3>No user data found. Please complete profile first.</h3>"

    before_w = user["before_weight"] or 0
    after_w = user["after_weight"] or 0

    if before_w > 0 and after_w > 0:
        if after_w < before_w:
            result = f"Weight Loss: {before_w - after_w} kg 🔥"
        elif after_w > before_w:
            result = f"Weight Gain: {after_w - before_w} kg 💪"
        else:
            result = "No Weight Change"
    else:
        result = "No data"

    content = f"""
    <h2>Welcome, {username}</h2>

    <p><b>Age:</b> {user["age"]}</p>
    <p><b>Weight:</b> {user["weight"]}</p>
    <p><b>Before Weight:</b> {before_w}</p>
    <p><b>After Weight:</b> {after_w}</p>

    <p><b>Progress:</b> {result}</p>

    <hr>

    <p><b>Plan:</b> {user["plan"]}</p>
    <p><b>Coach:</b> {user["coach"]}</p>
    <p><b>Workout:</b> {user["workout_type"]}</p>
    """

    return render_template_string(
        GLOBAL_LAYOUT,
        title="Dashboard",
        content=content,
        bg_url="https://images.unsplash.com/photo-1517836357463-d25dfeac3438?q=80&w=2070"
    )
    return render_template_string(GLOBAL_LAYOUT, title="Dashboard", content=content, bg_url="https://images.unsplash.com/photo-1517836357463-d25dfeac3438?q=80&w=2070")



    



from datetime import datetime

@app.route("/mark_attendance", methods=["POST"])
def mark_attendance():
    username = session.get('username')

    conn = sqlite3.connect("gym.db")
    cursor = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("INSERT INTO attendance (username, date) VALUES (?, ?)", (username, today))

    conn.commit()
    conn.close()

    return redirect(url_for('attendance'))

@app.route("/attendance_report")
def attendance_report():
    username = session.get('username')

    conn = sqlite3.connect("gym.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT date FROM attendance 
    WHERE username = ? 
    ORDER BY date DESC
    """, (username,))

    data = cursor.fetchall()
    conn.close()

    rows = "".join([f"<li>{d[0]}</li>" for d in data])

    content = f"""
    <h2>Monthly Attendance 📊</h2>
    <ul>{rows}</ul>
    """

    return render_template_string(GLOBAL_LAYOUT, title="Report", content=content, bg_url=BG_IMAGE)

@app.route("/buy_plan/<plan>")
def buy_plan(plan):
    username = session.get('username')

    conn = sqlite3.connect("gym.db")
    cursor = conn.cursor()

    cursor.execute("UPDATE users SET plan=? WHERE username=?", (plan, username))

    conn.commit()
    conn.close()

    return redirect(url_for('memberships'))

@app.route("/memberships")
def memberships():
    content = """
    <h2>Membership Plans 💳</h2>

    <ul>
        <li>Basic - ₹500 <a href="/buy_plan/Basic">Buy</a></li>
        <li>Standard - ₹1000 <a href="/buy_plan/Standard">Buy</a></li>
        <li>Premium - ₹1500 <a href="/buy_plan/Premium">Buy</a></li>
    </ul>
    """

    return render_template_string(GLOBAL_LAYOUT, title="Memberships", content=content, bg_url=BG_IMAGE)

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if not session.get('username'):
        return redirect("/member_login")

    username = session.get('username')
    db = get_db()

    # ✅ SAVE DATA (POST)
    if request.method == "POST":
        db.execute("""
        UPDATE users SET
            age=?,
            weight=?,
            before_weight=?,
            after_weight=?,
            coach=?,
            workout_type=?
        WHERE username=?
        """, (
            request.form["age"],
            request.form["weight"],
            request.form["before_weight"],
            request.form["after_weight"],
            request.form["coach"],
            request.form["workout_type"],
            username
        ))

        db.commit()

        return redirect("/dashboard")  # after saving

    # ✅ FETCH DATA (GET)
    user = db.execute(
        "SELECT * FROM users WHERE username=?",
        (username,)
    ).fetchone()

    # safety check
    if not user:
        return "<h3>No user found</h3>"

    content = f"""
    <h2>User Profile 👤</h2>

    <form method="POST" style="max-width:400px; margin:auto">
        <label>Age:</label>
        <input type="number" name="age" value="{user['age'] or ''}" required><br>

        <label>Current Weight:</label>
        <input type="number" name="weight" value="{user['weight'] or ''}" required><br>

        <label>Before Weight:</label>
        <input type="number" name="before_weight" value="{user['before_weight'] or ''}"><br>

        <label>After Weight:</label>
        <input type="number" name="after_weight" value="{user['after_weight'] or ''}"><br>

        <label>Coach:</label>
        <input type="text" name="coach" value="{user['coach'] or ''}"><br>

        <label>Workout Type:</label>
        <input type="text" name="workout_type" value="{user['workout_type'] or ''}"><br>

        <br>
        <button type="submit">Save Profile 💾</button>
    </form>
    """

    return render_template_string(GLOBAL_LAYOUT, title="Profile", content=content, bg_url=BG_IMAGE)

@app.route("/progress")
def progress():
    username = session.get('username')

    conn = sqlite3.connect("gym.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT age, weight, before_weight, after_weight, coach, workout_type
    FROM users WHERE username=?
    """, (username,))

    user = cursor.fetchone()
    conn.close()

    if user:
        age, weight, before_w, after_w, coach, workout = user

        gain_loss = float(after_w) - float(before_w)

        status = "Weight Gained 💪" if gain_loss > 0 else "Weight Lost 🔥"

        content = f"""
        <h2>Progress Dashboard 📊</h2>

        <div style="font-size:18px">
            <p><b>Age:</b> {age}</p>
            <p><b>Current Weight:</b> {weight} kg</p>
            <p><b>Before Weight:</b> {before_w} kg</p>
            <p><b>After Weight:</b> {after_w} kg</p>
            <p><b>Progress:</b> {gain_loss:.2f} kg ({status})</p>

            <hr>

            <p><b>Coach:</b> {coach}</p>
            <p><b>Workout Type:</b> {workout}</p>
        </div>
        """
    else:
        content = "<p>No data found</p>"

    return render_template_string(GLOBAL_LAYOUT, title="Progress", content=content, bg_url=BG_IMAGE)

with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)
   
@app.route('/qr')
def qr():
    url = "http://127.0.0.1:5000/register"

    img = qrcode.make(url)

    buf = BytesIO()
    img.save(buf)
    buf.seek(0)

    return send_file(buf, mimetype='image/png')

app.run(host="0.0.0.0", port=5000, debug=True)