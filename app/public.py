from flask import Blueprint, render_template, request, redirect, url_for, flash
from . import db
from .models import News, Fixture, ContactMessage

public_bp = Blueprint("public", __name__)

@public_bp.route("/public")
def home():
    latest_news = News.query.order_by(News.published_at.desc()).limit(3).all()
    upcoming = Fixture.query.filter_by(is_played=False).order_by(Fixture.match_date.asc()).limit(5).all()
    recent_results = Fixture.query.filter_by(is_played=True).order_by(Fixture.match_date.desc()).limit(5).all()

    return render_template(
        "public_home.html",
        latest_news=latest_news,
        upcoming=upcoming,
        recent_results=recent_results
    )

@public_bp.route("/public/news")
def news_list():
    items = News.query.order_by(News.published_at.desc()).all()
    return render_template("public_news.html", items=items)

@public_bp.route("/public/fixtures")
def fixtures_list():
    upcoming = Fixture.query.filter_by(is_played=False).order_by(Fixture.match_date.asc()).all()
    return render_template("public_fixtures.html", fixtures=upcoming)

@public_bp.route("/public/results")
def results_list():
    results = Fixture.query.filter_by(is_played=True).order_by(Fixture.match_date.desc()).all()
    return render_template("public_results.html", results=results)

@public_bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        message = request.form.get("message", "").strip()

        if not name or not email or not message:
            flash("All fields are required.", "danger")
            return redirect(url_for("public.contact"))

        msg = ContactMessage(name=name, email=email, message=message)
        db.session.add(msg)
        db.session.commit()

        flash("Your message has been sent to the club.", "success")
        return redirect(url_for("public.contact"))

    return render_template("contact.html")