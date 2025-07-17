from flask import Blueprint, render_template

interface_bp = Blueprint("interface", __name__,)  


@interface_bp.route("/")
def home():
    return render_template("Interface/home.html")

@interface_bp.route("/about")
def about():
    return render_template("Interface/about.html")


@interface_bp.route("/team")
def team():
    return render_template("Interface/team.html")


@interface_bp.route("/contact")
def contact():
    return render_template("Interface/contact.html")

@interface_bp.route("/feedback")
def feedback():
    return render_template("Interface/feedback.html")

@interface_bp.route("/faq")
def faq():
    return render_template("Interface/faq.html")


@interface_bp.route("/privacy")
def privacy():
    return render_template("Interface/privacy.html")



