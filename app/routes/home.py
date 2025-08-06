from flask import Blueprint, redirect, render_template, session, url_for

home_bp = Blueprint("home", __name__)

@home_bp.route("/home")
def home():
        return render_template("i_interface/home.html")

@home_bp.route("/int-test-500")
def test_500():
        return render_template("i_interface/error_500.html")

@home_bp.route("/int-test-404")
def test_404():
        return render_template("i_interface/error_404.html")

@home_bp.route("/db-test-500")
def test_db_500():
        return render_template("dashboard/error_500.html")

@home_bp.route("/db-test-404")
def test_db_404():
        return render_template("dashboard/error_404.html")