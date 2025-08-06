from app.models import get_feedbacks_collection
from app.models.contact import ContactMessage
from app.models.feedback import Feedback
from flask import Blueprint, render_template, request, flash, redirect, url_for
from app import mongo
from flask_mail import Message
from app import mail
from flask import current_app

interface_bp = Blueprint("interface", __name__,)  


@interface_bp.route("/")
def home():
    feedbacks = get_feedbacks_collection().find({"verified": True}).sort('_id', -1)
    testimonials = [Feedback(f) for f in feedbacks]
    return render_template('interface/home.html', feedbacks=testimonials)

@interface_bp.route("/about")
def about():
    return render_template("interface/about.html")


@interface_bp.route("/team")
def team():
    return render_template("interface/team.html")


@interface_bp.route('/contact', methods=['POST', 'GET'])
def contact():
    if request.method == 'POST':
        fullname = request.form['fullname']
        email = request.form['email']
        subject = request.form['subject']
        message = request.form['message']
        
        errors = ContactMessage.validate(fullname, email, subject, message)

        if errors:
            return render_template(
                "interface/contact.html",
                errors=errors,
                form_data={
                    'fullname': fullname,
                    'email': email,
                    'subject': subject,
                    'message': message
                }
            )


        mongo.db.contacts.insert_one({
            "fullname": fullname,
            "email": email,
            "subject": subject,
            "message": message
        })

        flash("Your message has been sent!")
        return redirect(url_for("interface.contact"))

    return render_template("interface/contact.html", errors={}, form_data={})
@interface_bp.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        rating = request.form.get('rating', '0')
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        message = request.form.get('message', '').strip()

        errors = Feedback.validate(name, email, message, rating)

        if errors:
            return render_template(
                "interface/feedback.html",
                errors=errors,
                form_data={'name': name, 'email': email, 'message': message, 'rating': rating}
            )

        feedback_id, token = Feedback.create_feedback(name, email, message, rating)

        verify_link = url_for('interface.verify_feedback', token=token, _external=True)

        msg = Message(
            subject="EdFlow: Please verify your feedback",
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[email]
        )
        msg.body = f"""
        Hello {name},

        Thank you for sharing your feedback with EdFlow.

        To publish your feedback on our site, please verify your email by clicking the link below:

        {verify_link}
        
        This Link will expires in 1 hour.

        If you did not submit this feedback, you can ignore this email.

        Best regards,
        The EdFlow Team
        """
        mail.send(msg)

        flash("Thank you! Please verify your email to publish your feedback.", "success")
        return redirect(url_for('interface.feedback'))  

    return render_template(
    'interface/feedback.html',
    errors={},  
    form_data={'name': '', 'email': '', 'message': '', 'rating': '0'}
)

@interface_bp.route('/verify-feedback/<token>')
def verify_feedback(token):
    if Feedback.verify_feedback(token):
        flash("✅ Your feedback has been verified and is now visible on our testimonials page.", "success")
        return redirect(url_for('interface.testimonials'))
    else:
        flash("❌ Invalid or expired verification link. Please submit your feedback again.", "danger")
        return redirect(url_for('interface.feedback'))
 
@interface_bp.route('/testimonials')
def testimonials():
    feedbacks = get_feedbacks_collection().find({"verified": True}).sort('_id', -1)
    testimonials = [Feedback(f) for f in feedbacks]
    return render_template('interface/testimonials.html', testimonials=testimonials)

@interface_bp.route("/faq")
def faq():
    return render_template("interface/faq.html")


@interface_bp.route("/privacy")
def privacy():
    return render_template("interface/privacy.html")



