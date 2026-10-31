import json
import os
from functools import wraps
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from database import (
    add_user,
    create_database,
    find_user,
    get_all_movies,
    get_movie_poster_record,
    get_similar_movies,
    movie_exists,
    save_movie_poster,
    search_movies,
)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")


def get_tmdb_api_key():
    for key in ("TMDB_API_KEY", "tmdb_api_key"):
        value = os.environ.get(key)
        if value and value.strip():
            return value.strip()

    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = [part.strip() for part in stripped.split("=", 1)]
            normalized_key = key.removeprefix("export ")
            if normalized_key in {"TMDB_API_KEY", "tmdb_api_key"} and value:
                os.environ[normalized_key] = value
                return value
    return None


create_database()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template(
        "index.html",
        username=session["username"],
        movies=get_all_movies(),
        tmdb_api_enabled=bool(get_tmdb_api_key()),
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Enter a username and password.", "error")
            return render_template("register.html"), 400
        if len(username) > 50:
            flash("Usernames must be 50 characters or fewer.", "error")
            return render_template("register.html"), 400
        if len(password) < 8:
            flash("Your password must be at least 8 characters long.", "error")
            return render_template("register.html"), 400

        normalized_username = username.casefold()
        if find_user(normalized_username) is not None:
            flash("That username is already registered.", "error")
            return render_template("register.html"), 409

        if not add_user(username, generate_password_hash(password)):
            flash("That username is already registered.", "error")
            return render_template("register.html"), 409

        flash("Registration successful! You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = find_user(username.casefold())

        if user is None or not check_password_hash(user["password"], password):
            flash("Incorrect username or password.", "error")
            return render_template("login.html"), 401

        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        flash("Login successful!", "success")
        return redirect(url_for("index"))

    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.get("/search")
@login_required
def search():
    return jsonify(search_movies(request.args.get("q", "")))


@app.get("/recommend/<int:movie_id>")
@login_required
def recommend(movie_id):
    if not movie_exists(movie_id):
        return jsonify({"error": "Movie not found."}), 404
    recommendations = get_similar_movies(movie_id)
    return jsonify(recommendations)


@app.get("/poster/<int:movie_id>")
@login_required
def movie_poster(movie_id):
    movie = get_movie_poster_record(movie_id)
    if movie is None:
        abort(404)

    refresh = request.args.get("refresh") == "1"
    if movie["poster"] and not refresh:
        return redirect(movie["poster"], code=302)

    tmdb_api_key = get_tmdb_api_key()
    if not tmdb_api_key or movie["tmdb_id"] is None:
        abort(404)

    query = urlencode({"api_key": tmdb_api_key})
    request_url = f"https://api.themoviedb.org/3/movie/{movie['tmdb_id']}?{query}"
    tmdb_request = Request(
        request_url,
        headers={"Accept": "application/json", "User-Agent": "MovieHub/1.0"},
    )
    try:
        with urlopen(tmdb_request, timeout=6) as response:
            movie_details = json.load(response)
    except HTTPError as error:
        app.logger.warning(
            "TMDB poster lookup failed for movie %s with HTTP %s.",
            movie["tmdb_id"],
            error.code,
        )
        abort(502)
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        app.logger.warning(
            "TMDB poster lookup failed for movie %s: %s",
            movie["tmdb_id"],
            error,
        )
        abort(502)

    if not isinstance(movie_details, dict):
        app.logger.error(
            "TMDB returned an invalid poster response for movie %s.",
            movie["tmdb_id"],
        )
        abort(502)

    poster_path = movie_details.get("poster_path")
    if not isinstance(poster_path, str) or not poster_path.startswith("/"):
        abort(404)

    poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
    save_movie_poster(movie_id, poster_url)
    return redirect(poster_url, code=302)


if __name__ == "__main__":
    app.run(debug=True)
