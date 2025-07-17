from flask import Blueprint, redirect, render_template, session, url_for

home_bp = Blueprint("home", __name__)

@home_bp.route("/home")
def home():
        return render_template("interface/home.html")
   