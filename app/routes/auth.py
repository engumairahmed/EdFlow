from datetime import datetime, timedelta, timezone 
import logging
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


logger = logging.getLogger(__name__)

# Dummy email verification storage (in-memory for now)
verification_codes = {}

users=mongo.db['users']
db=mongo.db

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
            try:
                users.insert_one({
                "username": username,
                "email":email,
                "password": hashed,
                "role": role,
                "is_verified": False,
                "createdAt": datetime.now(timezone.utc),
                "lastLogin": datetime.now(timezone.utc)
                })
            except Exception as e:
                flash("Error occurred while registering user.", "danger")
                logger.info(f"Error registering user: {e}")
                return redirect(url_for('auth.register'))
            
            # Generate OTP and store temporarily
            code = str(random.randint(100000, 999999))
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=60) # Code expires in 60 minutes
            try:
                db.otp_codes.insert_one({
                "email": email,
                "code": code,
                "created_at": datetime.now(timezone.utc),
                "expires_at": expires_at
            })
            except Exception as e:
                flash("Error occurred while generating OTP.", "danger")
                logger.info(f"Error generating OTP: {e}")
                return redirect(url_for('auth.register'))
            session['email_to_verify'] = email  # store in session for verify-email page

            # Send code via email
            try:
                msg = Message("Email Verification Code", recipients=[email])
                msg.body = f"Your verification code is: {code}"
                mail.send(msg)
            except Exception as e:
                flash("Error occurred while sending verification code.", "danger")
                logger.info(f"Error sending verification code: {e}")
                return redirect(url_for('auth.register'))

            flash("Verification code sent to your email. Please verify to continue.", "info")
            logger.info(f"Verification code sent to {email}")
            return redirect(url_for('auth.verify_email'))

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
            logger.info("User session expired")
            return redirect(url_for('auth.login'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = users.find_one({'email': email})

        if user and check_password_hash(user['password'], password):
            if not user.get('is_verified', False):
                session['email_to_verify'] = email
                flash("Please verify your email before logging in.", "warning")
                logger.info(f"User {email} is not verified")
                return redirect(url_for('auth.verify_email'))
                
            remember_me = True if request.form.get("remember_me") else False

            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            session['role'] = user['role']
            session['plan'] = user.get('plan', 'free')

            session.permanent = remember_me
            
            mongo.db.login_logs.insert_one({
                'user_id': str(user['_id']),
                'username': user['username'],
                'role': user['role'],
                'timestamp': datetime.now()
            })

            return redirect(url_for('dashboard.dashboard_view'))

        flash("Invalid email or password", "danger")
        logger.info("Invalid email or password")
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
            return render_template('change_password.html')
        elif new != confirm:
            flash("New passwords do not match.", "danger")
            return render_template('change_password.html')
        elif len(new) < 6:
            flash("New password must be at least 6 characters long.", "danger")
            return render_template('change_password.html')
        else:
            hashed = generate_password_hash(new)
            mongo.db.users.update_one({'_id': user['_id']}, {'$set': {'password': hashed}})
            flash("Password updated successfully. Please log in again.", "success")
            return redirect(url_for('auth.logout'))

    return render_template('change_password.html')


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
    email = session.get('email_to_verify')

    # --- GET Request ---
    # Redirect if there's no email to verify in the session.
    if request.method == 'GET':
        if not email:
            flash('Please register or log in to verify your email.', 'info')
            return redirect(url_for('auth.login'))
        return render_template('auth/verify-email.html')

    # --- POST Request ---
    if request.method == 'POST':
        code = request.form.get('code')

        # Basic input and session validation
        if not code or not email:
            flash('Invalid request or session expired. Please try again.', 'danger')
            return redirect(url_for('auth.login'))

        # Find the verification code in the database
        verification_entry = db.otp_codes.find_one({'email': email})

        if not verification_entry:
            flash('Invalid or expired verification code.', 'danger')
            return render_template('auth/verify-email.html')

        # Check for code expiration
        if verification_entry['expires_at'].tzinfo is None:
            expires_at = verification_entry['expires_at'].replace(tzinfo=timezone.utc)
        else:
            expires_at = verification_entry['expires_at']

        if expires_at < datetime.now(timezone.utc):
            # Code has expired, delete it and prompt for a new one
            db.otp_codes.delete_one({'email': email})
            flash('Verification code has expired. Please request a new one.', 'danger')
            return redirect(url_for('auth.resend_code'))

        # Check if the submitted code matches the stored code
        if code == verification_entry['code']:
            # Find the user and update their verification status
            user = db.users.find_one({'email': email})
            if user:
                db.users.update_one({'email': email}, {'$set': {'is_verified': True}})
            else:
                logger.error(f"User with email {email} not found during verification.")
                flash('User not found. Please register again.', 'danger')
                return redirect(url_for('auth.register'))

            # Clean up after successful verification
            db.otp_codes.delete_one({'email': email})
            session.pop('email_to_verify', None)
            flash('Email verified successfully! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        else:
            # Incorrect code
            flash('Invalid verification code.', 'danger')
            return render_template('auth/verify-email.html')

# =============================
# RESEND CODE
# =============================
@auth_bp.route('/resend-code', methods=['GET', 'POST'])
def resend_code():
    # Safely get the email from the session.
    # If the email is not in the session, the user is not in the verification flow.
    email = session.get('email_to_verify')
    if not email:
        flash('Session expired. Please log in or register again.', 'danger')
        return redirect(url_for('auth.login'))

    # Check if a user with this email actually exists and is unverified.
    user = db.users.find_one({"email": email, "is_verified": False})
    if not user:
        # If the user is already verified or doesn't exist, we should redirect them.
        flash('This email is already verified or does not exist.', 'warning')
        session.pop('email_to_verify', None)
        return redirect(url_for('auth.login'))

    # Generate a new OTP
    code = str(random.randint(100000, 999999))
    
    # Define a new expiration time (e.g., 60 minutes from now)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=60)

    try:
        # Update or insert the new OTP in the database.
        # This is more robust than a global dictionary.
        db.otp_codes.update_one(
            {"email": email},
            {"$set": {"code": code, "expires_at": expires_at}},
            upsert=True
        )
        
        # Send the new verification code via email.
        msg = Message(
            subject="EdFlow: Your New Verification Code",
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[email]
        )
        msg.body = f"""
            To verify your email, please use the code below:

            {code}
            
            This code will expire in 60 minutes.

            If you did not request this, you can safely ignore this email.

            Best regards,
            The EdFlow Team
            """
        mail.send(msg)
        
        flash('A new verification code has been sent to your email.', 'info')
        logging.info(f"New verification code sent to {email}")

    except Exception as e:
        flash('Failed to send a new verification code. Please try again.', 'danger')
        logging.error(f"Failed to send resend email to {email}: {e}")
    
    # Redirect back to the verification page to enter the new code.
    return redirect(url_for('auth.verify_email'))

# =============================
# LOGOUT
# =============================
@auth_bp.route('/logout')
def logout():
    session.clear()  # Clears all session data
    return redirect(url_for('auth.login'))
