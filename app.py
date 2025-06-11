from flask import Flask, g, jsonify, render_template, request, redirect, url_for, flash
import mysql.connector
from mysql.connector import Error
import socket
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Required for flash messages

# MySQL Configuration with timeout settings
MYSQL_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'doxpro1_jeivs_db',
    'connect_timeout': 10,  # Connection timeout in seconds
    'connection_timeout': 10,  # Connection timeout for operations
    'use_pure': True
}

# SMTP configuration (replace with your actual credentials)
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USERNAME = 'vaishbhule0427@gmail.com'  # Replace with your email
SMTP_PASSWORD = 'tgyq hboq evdv qnas'
SENDER_EMAIL = 'vaishbhule0427@gmail.com'    # Same as above or another sender

def check_host_availability(host, port=3306):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        return False

# Function to get DB connection
def get_db():
    try:
        # First check if host is reachable
        if not check_host_availability(MYSQL_CONFIG['host']):
            print(f"Cannot reach MySQL server at {MYSQL_CONFIG['host']}")
            return None

        db = getattr(g, '_database', None)
        if db is None:
            db = g._database = mysql.connector.connect(**MYSQL_CONFIG)
        return db
    except Error as e:
        error_msg = str(e)
        if "Can't connect to MySQL server" in error_msg:
            print(f"Network error: Cannot connect to MySQL server at {MYSQL_CONFIG['host']}")
        elif "Access denied" in error_msg:
            print("Authentication error: Wrong username or password")
        else:
            print(f"Database error: {error_msg}")
        return None

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/test-connection')
def test_connection():
    try:
        # First check if host is reachable
        if not check_host_availability(MYSQL_CONFIG['host']):
            return jsonify({
                'status': 'error',
                'message': f"Cannot reach MySQL server at {MYSQL_CONFIG['host']}. Please check if MySQL is running and the host is correct."
            })

        conn = get_db()
        if conn is None:
            return jsonify({
                'status': 'error',
                'message': 'Failed to connect to database. Please check your MySQL server is running and credentials are correct.'
            })
        
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        return jsonify({
            'status': 'success',
            'message': 'Successfully connected to database',
            'server_info': {
                'host': MYSQL_CONFIG['host'],
                'database': MYSQL_CONFIG['database']
            }
        })
    except Error as e:
        return jsonify({
            'status': 'error',
            'message': f'Database error: {str(e)}',
            'error_type': 'connection_error'
        })

@app.route('/')
def index():
    try:
        conn = get_db()
        if conn is None:
            return render_template('index.html', message={'type': 'danger', 'text': 'Database connection failed'})

        cursor = conn.cursor(dictionary=True)
        ref_number = request.args.get('ref_number', '')
        if ref_number:
            cursor.execute("SELECT * FROM paper_request WHERE ref_number = %s", (ref_number,))
        else:
            cursor.execute("SELECT * FROM paper_request")
        rows = cursor.fetchall()
        columns = [i[0] for i in cursor.description] if cursor.description else []
        # Pass the first record if searching by ref_number
        record = rows[0] if ref_number and rows else None
        return render_template('index.html', rows=rows, columns=columns, record=record)
    except Error as e:
        return render_template('index.html', message={'type': 'danger', 'text': f'Database error: {str(e)}'})

@app.route('/get/<int:id>')
def get_record(id):
    try:
        conn = get_db()
        if conn is None:
            return jsonify({'error': 'Database connection failed'}), 500

        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM paper_request WHERE id = %s", (id,))
        record = cursor.fetchone()
        
        if record:
            return jsonify(record)
        return jsonify({'error': 'Record not found'}), 404
    except Error as e:
        return jsonify({'error': str(e)}), 500

@app.route('/add', methods=['POST'])
def add_record():
    try:
        conn = get_db()
        if conn is None:
            flash('Database connection failed', 'danger')
            return redirect(url_for('index'))

        cursor = conn.cursor()
        ref_number = request.form['ref_number']
        title = request.form['title']
        description = request.form['description']

        cursor.execute(
            "INSERT INTO paper_request (ref_number, title, description) VALUES (%s, %s, %s)",
            (ref_number, title, description)
        )
        conn.commit()
        
        flash('Record added successfully', 'success')
        return redirect(url_for('index'))
    except Error as e:
        flash(f'Error adding record: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/edit', methods=['POST'])
def edit_record():
    try:
        conn = get_db()
        if conn is None:
            flash('Database connection failed', 'danger')
            return redirect(url_for('index'))

        cursor = conn.cursor()
        id = request.form['id']
        ref_number = request.form['ref_number']
        title = request.form['title']
        description = request.form['description']

        cursor.execute(
            "UPDATE paper_request SET ref_number = %s, title = %s, description = %s WHERE id = %s",
            (ref_number, title, description, id)
        )
        conn.commit()
        
        flash('Record updated successfully', 'success')
        return redirect(url_for('index'))
    except Error as e:
        flash(f'Error updating record: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete_record(id):
    try:
        conn = get_db()
        if conn is None:
            flash('Database connection failed', 'danger')
            return redirect(url_for('index'))

        cursor = conn.cursor()
        cursor.execute("DELETE FROM paper_request WHERE id = %s", (id,))
        conn.commit()
        
        flash('Record deleted successfully', 'success')
        return redirect(url_for('index'))
    except Error as e:
        flash(f'Error deleting record: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/send_mail', methods=['POST'])
def send_mail():
    email_id = request.form['email_id']
    author = request.form['author']
    ref_number = request.form['ref_number']
    title = request.form['title']

    # First email subject and body
    subject1 = "Your Paper Under Review - JEIVS"
    body1 = f'''
    <div style="font-family:'Segoe UI', 'Poppins', Arial, sans-serif; font-size:1rem; color:#000000;">
        <p style="margin-bottom: 24px;">Dear <b>{author}</b>,</p>
        <p style="margin-bottom: 24px;">
            We are pleased to inform you that your submitted paper is now under review in <b>JEIVS</b>. Our reviewers are evaluating your manuscript, and if any clarifications or modifications are needed, they will reach out to you directly.
        </p>
        <p style="margin-bottom: 16px;">
            <b>Paper ID : {ref_number}</b>
        </p>
        <p style="margin-bottom: 32px;">
            <b>Project Title: [{title}]</b>
        </p>
        <p style="margin-bottom: 32px;">
            We appreciate your patience and cooperation during this process. If you have any questions, feel free to contact us.
        </p>
        <p style="margin-bottom: 8px;">
            Best regards,<br>
            <b>Editorial Team</b><br>
            <b>Journal of Embedded Intelligence and Vision Systems (JEIVS)</b>
        </p>
        <p style="margin-top: 16px;">
            <img src="https://cdn-icons-png.flaticon.com/512/561/561127.png" alt="mail" style="width:22px;vertical-align:middle;margin-right:6px;"> <a href="https://www.jeivs.in" target="_blank" style="color:#1a0dab; font-size:1.08rem; text-decoration:underline;">www.jeivs.in</a>
        </p>
    </div>
    '''

    # Second email subject and body
    subject2 = "Final steps for publication - Payment & Manuscript Submission - JEIVS"
    body2 = f'''
    <div style="font-family:'Segoe UI', 'Poppins', Arial, sans-serif; font-size:1rem; color:#000000; margin-top:48px;">
        <p>Dear <b>{author}</b>,</p>
        <p style="margin-bottom: 18px;">
            We are pleased to inform you that your paper is currently <b>under the review process in JEIVS Journal</b> as part of our double-blind peer review. Kindly check the <b>comments from the reviewer</b> on your manuscript and make necessary revisions if required.
        </p>
        <p style="margin-bottom: 10px;"><b>Paper Title : [ {title} ]</b></p>
        <p style="margin-bottom: 10px;"><b>Reviewer  Comment :</b> <a href="https://www.jeivs.in/reviewer-comment" target="_blank" style="color:#1a0dab; text-decoration:underline;">Your research contribution aligns well with the scope of our journal.</a></p>
        <p style="margin-bottom: 10px;">Next Steps:</p>
        <ul style="list-style:none; padding-left:0; margin-bottom:18px;">
            <li style="margin-bottom:10px;">
                <span style="font-size:1.2em;">✔️</span> <b>Made the payment</b> via : <a href="https://pages.razorpay.com/stores/Jevis" target="_blank" style="color:#1a0dab; text-decoration:underline;">CLICK HERE</a> and pay  APC  or through our website: <a href="https://www.jeivs.in" target="_blank" style="color:#1a0dab; text-decoration:underline;">www.jeivs.in</a>.
            </li>
            <li style="margin-bottom:10px;">
                <span style="font-size:1.2em;">✔️</span> <b>Updated your manuscript</b> as per the JEIVS standard format <a href="https://docs.google.com/document/d/1y679ko-icNYbUJy8hFW-WxsDMZ-zLfDvP5HvTMCvsLc/edit?tab=t.0" target="_blank" style="color:#1a0dab; text-decoration:underline;">[CLICK HERE]</a>. Share only Word format.
            </li>
            <li style="margin-bottom:10px;">
                <span style="font-size:1.2em;">✔️</span> <b>Signed and submitted</b> the Copyright Transfer Form along with your final manuscript. (<a href="https://docs.google.com/document/d/1_Auj-bq3mMkEVD1k4jMaK_JsSeYrlLbyWD8KyQxPgz4/edit?tab=t.0#heading=h.dodt3cp2q8x" target="_blank" style="color:#1a0dab; text-decoration:underline;">CLICK HERE</a>)
            </li>
        </ul>
        <p style="margin-bottom: 18px;">Please complete the process at the earliest to avoid any delay in publication. Attached all the three document over this email only in 3 days.</p>
        <p style="margin-bottom: 18px;">For any assistance, feel free to reach out.</p>
        <p style="margin-bottom: 8px;">Best regards,<br>
            <b>Editorial Team</b><br>
            <b>JEIVS Journal</b>
        </p>
        <p style="margin-top: 16px;">
            <img src="https://cdn-icons-png.flaticon.com/512/561/561127.png" alt="mail" style="width:22px;vertical-align:middle;margin-right:6px;"> <a href="https://www.jeivs.in" target="_blank" style="color:#1a0dab; font-size:1.08rem; text-decoration:underline;">www.jeivs.in</a>
        </p>
    </div>
    '''

    # Send first email
    msg1 = MIMEMultipart()
    msg1['From'] = SENDER_EMAIL
    msg1['To'] = email_id
    msg1['Subject'] = subject1
    msg1.attach(MIMEText(body1, 'html'))

    # Send second email
    msg2 = MIMEMultipart()
    msg2['From'] = SENDER_EMAIL
    msg2['To'] = email_id
    msg2['Subject'] = subject2
    msg2.attach(MIMEText(body2, 'html'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SENDER_EMAIL, email_id, msg1.as_string())
            server.sendmail(SENDER_EMAIL, email_id, msg2.as_string())
        flash('Emails sent successfully!', 'success')
    except Exception as e:
        flash(f'Failed to send emails: {str(e)}', 'danger')

    return redirect(url_for('index', ref_number=ref_number))

if __name__ == '__main__':
    app.run(debug=True)
