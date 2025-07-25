from flask import Blueprint, redirect, render_template, request, jsonify, session, flash, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import re
import random
from flask_mail import Message
from app import mail  # import mail from app.py
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask import current_app
from app import mongo


auth_bp = Blueprint("auth", __name__, url_prefix='/auth')

# Dummy email verification storage (in-memory for now)
verification_codes = {}

users=mongo.db['users']

# =============================
# REGISTER ROUTE
# =============================
@auth_bp.route('/register', methods=['POST','GET'])
def register():
    if not session.get('user_id'):
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            email = request.form['email']
            role = request.form['role']
 

            if users.find_one({"email": email}):
                flash("User already exists.", "danger")
                return redirect(url_for('auth.register'))

            hashed = generate_password_hash(password)

            users.insert_one({
                "username": username,
                "email":email,
                "password": hashed,
                "role": role,
                "is_verified": False
                })
            
            # Generate OTP and store temporarily
            code = str(random.randint(100000, 999999))
            verification_codes[email] = code
            session['email_to_verify'] = email  # store in session for verify-email page

            # Send code via email
            msg = Message("Email Verification Code", recipients=[email])
            msg.body = f"Your verification code is: {code}"
            mail.send(msg)

            flash("Verification code sent to your email. Please verify to continue.", "info")

            return render_template('auth/login.html')
        return render_template('auth/register.html')
    return redirect(url_for('dashboard.dashboard_view'))
# =============================
# LOGIN ROUTE
# =============================
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        # Check that the user still exists in DB
        user = users.find_one({'_id': session['user_id']})
        if user:
            return redirect(url_for('dashboard.dashboard_view'))
        else:
            # User not found → clear session and show login again
            session.clear()
            flash("Your session has expired. Please login again.", "warning")
            return redirect(url_for('auth.login'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = users.find_one({'email': email})

        if user and check_password_hash(user['password'], password):
            remember_me = True if request.form.get("remember_me") else False

            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            session['role'] = user['role']
            session['plan'] = user.get('plan', 'free')

            print("Logged in user ID:", session['user_id'])

            session.permanent = remember_me

            return redirect(url_for('dashboard.dashboard_view'))

        flash("Invalid email or password", "danger")
        return render_template('auth/login.html')

    return render_template('auth/login.html')

# Token serializer
def get_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

# =============================
# FORGOT PASSWORD
# =============================
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')

        if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash('Please enter a valid email address.', 'danger')
            return redirect(url_for('auth.forgot_password'))

        user = users.find_one({"email": {"$regex": f"^{email}$", "$options": "i"}})

        if user:
            serializer = get_serializer()
            token = serializer.dumps(email, salt='password-reset-salt')
            reset_link = url_for('auth.reset_password', token=token, _external=True)

            msg = Message('Password Reset Request', recipients=[email])
            msg.body = f"Click the link below to reset your password:\n\n{reset_link}\n\nLink expires in 1 hour."
            mail.send(msg)

            flash('A password reset link has been sent to your email.', 'success')
        else:
            flash('This email is not registered.', 'danger')

        return redirect(url_for('auth.forgot_password'))

    return render_template('auth/forgot.html')

# =============================
# UPDATE PASSWORD
# =============================
@auth_bp.route('/update-password', methods=['GET', 'POST'])
def update_password():
    if 'username' not in session:
        flash("Login required to update password", "danger")
        return redirect(url_for('auth.login'))

    user = mongo.db.users.find_one({'username': session['username']})
    if not user:
        flash("User not found", "danger")
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        current = request.form.get('current_password')
        new = request.form.get('new_password')
        confirm = request.form.get('confirm_password')

        if not check_password_hash(user['password'], current):
            flash("Current password is incorrect.", "danger")
        elif new != confirm:
            flash("New passwords do not match.", "danger")
        elif len(new) < 6:
            flash("New password must be at least 6 characters long.", "danger")
        else:
            hashed = generate_password_hash(new)
            mongo.db.users.update_one({'_id': user['_id']}, {'$set': {'password': hashed}})
            flash("Password updated successfully. Please log in again.", "success")
            return redirect(url_for('auth.logout'))

    return render_template('update_password.html')


# =============================
# RESET PASSWORD VIA TOKEN
# =============================
@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = get_serializer().loads(token, salt='password-reset-salt', max_age=3600)
    except SignatureExpired:
        flash("The password reset link has expired.", "danger")
        return redirect(url_for('auth.forgot_password'))
    except BadSignature:
        flash("Invalid password reset link.", "danger")
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm = request.form.get('confirm')

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return redirect(request.url)

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(request.url)

        hashed_password = generate_password_hash(password)
        users.update_one({'email': email}, {'$set': {'password': hashed_password}})

        flash("Password reset successfully. Please login.", "success")
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html')


# =============================
# VERIFY EMAIL (OTP CODE)
# =============================
@auth_bp.route('/verify-email', methods=['GET', 'POST'])
def verify_email():
    if request.method == 'POST':
        code = request.form.get('code')
        email = request.form.get('email')

        if not email:
            flash('Session expired or no email provided.', 'danger')
            return redirect(url_for('auth.login'))

        correct_code = verification_codes.get(email)
        if code == correct_code:
            flash('Email verified successfully!', 'success')
            verification_codes.pop(email, None)
            return redirect(url_for('auth.login'))
        else:
            flash('Invalid verification code.', 'danger')

    return render_template('auth/verify-email.html')


# =============================
# RESEND CODE
# =============================
@auth_bp.route('/resend-code', methods=['GET'])
def resend_code():
    email = request.args.get('email')
    if not email:
        flash('Email is required to resend code.', 'danger')
        return redirect(url_for('auth.login'))

    code = str(random.randint(100000, 999999))
    verification_codes[email] = code

    print(f"[DEBUG] Sending verification code {code} to {email}")  # Replace with email logic
    flash('A new verification code has been sent to your email.', 'info')
    return redirect(url_for('auth.verify_email'))

# =============================
# LOGOUT
# =============================
@auth_bp.route('/logout')
def logout():
    session.clear()  # Clears all session data
    return redirect(url_for('auth.login'))
