import csv
import json
import sqlite3
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
DATABASE = PROJECT_DIR / "movie_recommendations.sqlite3"
MOVIES_CSV = PROJECT_DIR / "movies.db" / "tmdb_5000_movies.csv"
CREDITS_CSV = PROJECT_DIR / "movies.db" / "tmdb_5000_credits.csv"


def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            genre TEXT NOT NULL,
            rating REAL NOT NULL,
            description TEXT,
            poster TEXT,
            tmdb_id INTEGER,
            tags TEXT NOT NULL DEFAULT ''
        )
        """
    )

    movie_columns = {
        row["name"] for row in cursor.execute("PRAGMA table_info(movies)").fetchall()
    }
    if "tmdb_id" not in movie_columns:
        cursor.execute("ALTER TABLE movies ADD COLUMN tmdb_id INTEGER")
    if "tags" not in movie_columns:
        cursor.execute("ALTER TABLE movies ADD COLUMN tags TEXT NOT NULL DEFAULT ''")
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_movies_tmdb_id ON movies(tmdb_id)"
    )
    try:
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_ci ON users(LOWER(username))"
        )
    except sqlite3.IntegrityError:
        pass

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            movie_id INTEGER NOT NULL,
            UNIQUE(user_id, movie_id),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(movie_id) REFERENCES movies(id)
        )
        """
    )

    movies = [
        (
            "Interstellar",
            "Sci-Fi",
            8.7,
            "A group of astronauts travels through a wormhole in search of a new home.",
            "https://image.tmdb.org/t/p/w500/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg",
        ),
        (
            "Inception",
            "Sci-Fi",
            8.8,
            "A skilled thief enters the dreams of others to steal valuable secrets.",
            "https://image.tmdb.org/t/p/w500/oYuLEt3zVCKq57qu2F8dT7NIa6f.jpg",
        ),
        (
            "The Dark Knight",
            "Action",
            9.0,
            "Batman faces the dangerous criminal mastermind known as the Joker.",
            "https://image.tmdb.org/t/p/w500/qJ2tW6WMUDux911r6m7haRef0WH.jpg",
        ),
        (
            "Avengers: Endgame",
            "Action",
            8.4,
            "The Avengers attempt to undo the destruction caused by Thanos.",
            "https://image.tmdb.org/t/p/w500/or06FN3Dka5tukK1e9sl16pB3iy.jpg",
        ),
        (
            "Titanic",
            "Romance",
            7.9,
            "A young couple falls in love aboard the famous Titanic ship.",
            "https://image.tmdb.org/t/p/w500/9xjZS2rlVxm8SFx8kPC3aIGCOYQ.jpg",
        ),
        (
            "The Notebook",
            "Romance",
            7.8,
            "A touching love story between two young people.",
            "https://image.tmdb.org/t/p/w500/qom1SZSMM28VQ3Yb9j9k0K6w6uK.jpg",
        ),
        (
            "3 Idiots",
            "Comedy",
            8.4,
            "Three college friends experience friendship, education and life.",
            "https://image.tmdb.org/t/p/w500/66A9MqXOyVFCssoloscw3W9Q2qG.jpg",
        ),
        (
            "PK",
            "Comedy",
            8.1,
            "An innocent alien tries to understand human society and its traditions.",
            "https://image.tmdb.org/t/p/w500/z2x2Y4tn7p5pL6W2fR2D8X0e8Y.jpg",
        ),
        (
            "Dangal",
            "Drama",
            8.3,
            "A father trains his daughters to become successful wrestlers.",
            "https://image.tmdb.org/t/p/w500/p2lV8LhZs1wL5FQ5pJ6D5Y9R2f.jpg",
        ),
        (
            "Taare Zameen Par",
            "Drama",
            8.3,
            "A teacher discovers the hidden talent of a young student.",
            "https://image.tmdb.org/t/p/w500/26G3C5L8N4v6Q8S2xR8T0Y2A.jpg",
        ),
        (
            "Joker",
            "Drama",
            8.4,
            "A troubled man slowly transforms into the criminal Joker.",
            "https://image.tmdb.org/t/p/w500/udDclJoHjfjb8Ekgsd4FDteOkCU.jpg",
        ),
        (
            "Guardians of the Galaxy",
            "Action",
            8.0,
            "A group of unusual heroes joins together to save the galaxy.",
            "https://image.tmdb.org/t/p/w500/r7vmZjiyZw9rpJMQJdXpjgiCOk9.jpg",
        ),
    ]

    count = cursor.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
    if count == 0:
        cursor.executemany(
            """
            INSERT INTO movies (title, genre, rating, description, poster)
            VALUES (?, ?, ?, ?, ?)
            """,
            movies,
        )

    try:
        import_tmdb_movies(cursor)
        conn.commit()
    finally:
        conn.close()


def import_tmdb_movies(cursor):
    if not MOVIES_CSV.is_file():
        return

    existing_tmdb_ids = {
        row["tmdb_id"]
        for row in cursor.execute(
            "SELECT tmdb_id FROM movies WHERE tmdb_id IS NOT NULL"
        ).fetchall()
    }

    with MOVIES_CSV.open(encoding="utf-8-sig", newline="") as movies_file:
        movie_rows = list(csv.DictReader(movies_file))
    dataset_ids = {int(row["id"]) for row in movie_rows if row.get("id")}
    missing_tmdb_ids = dataset_ids - existing_tmdb_ids
    if not missing_tmdb_ids:
        return

    cast_by_movie_id = {}
    if CREDITS_CSV.is_file():
        with CREDITS_CSV.open(encoding="utf-8-sig", newline="") as credits_file:
            for credit in csv.DictReader(credits_file):
                movie_id = int(credit["movie_id"])
                if movie_id not in missing_tmdb_ids:
                    continue
                cast = json.loads(credit.get("cast") or "[]")
                cast_by_movie_id[movie_id] = [
                    person["name"]
                    for person in cast[:10]
                    if person.get("name")
                ]

    existing_titles = {}
    for movie in cursor.execute(
        "SELECT id, title, tmdb_id FROM movies"
    ).fetchall():
        existing_titles.setdefault(
            movie["title"].strip().casefold(),
            (movie["id"], movie["tmdb_id"]),
        )

    for row in movie_rows:
        title = row.get("title", "").strip()
        if not title:
            continue

        tmdb_id = int(row["id"])
        if tmdb_id in existing_tmdb_ids:
            continue

        genres = [
            item["name"]
            for item in json.loads(row.get("genres") or "[]")
            if item.get("name")
        ]
        keywords = [
            item["name"]
            for item in json.loads(row.get("keywords") or "[]")
            if item.get("name")
        ]
        tags = list(
            dict.fromkeys(keywords + cast_by_movie_id.get(tmdb_id, []))
        )
        genre = ", ".join(genres) if genres else "Unknown"
        description = row.get("overview", "").strip()
        try:
            rating = float(row.get("vote_average") or 0)
        except ValueError as error:
            raise ValueError(
                f"Invalid rating for TMDB movie {tmdb_id} ({title!r})."
            ) from error

        existing = existing_titles.get(title.casefold())
        if existing and existing[1] is None:
            movie_id = existing[0]
            cursor.execute(
                """
                UPDATE movies
                SET genre = ?, rating = ?, description = ?, tmdb_id = ?, tags = ?
                WHERE id = ?
                """,
                (genre, rating, description, tmdb_id, " | ".join(tags), movie_id),
            )
            existing_titles[title.casefold()] = (movie_id, tmdb_id)
            existing_tmdb_ids.add(tmdb_id)
            continue
        if existing and existing[1] == tmdb_id:
            continue

        cursor.execute(
            """
            INSERT INTO movies (title, genre, rating, description, tmdb_id, tags)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, genre, rating, description, tmdb_id, " | ".join(tags)),
        )
        existing_titles[title.casefold()] = (cursor.lastrowid, tmdb_id)
        existing_tmdb_ids.add(tmdb_id)


def add_user(username, password):
    conn = get_connection()
    normalized_username = (username or "").strip()
    try:
        conn.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (normalized_username, password),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def find_user(username):
    conn = get_connection()
    normalized_username = (username or "").strip()
    user = conn.execute(
        "SELECT * FROM users WHERE LOWER(username) = LOWER(?)",
        (normalized_username,),
    ).fetchone()
    conn.close()
    return dict(user) if user else None


def get_movie_poster_record(movie_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT id, tmdb_id, poster FROM movies WHERE id = ?",
        (movie_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def save_movie_poster(movie_id, poster_url):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE movies SET poster = ? WHERE id = ?",
            (poster_url, movie_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_movies():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM movies ORDER BY rating DESC, id LIMIT 24"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def search_movies(query):
    conn = get_connection()
    keyword = f"%{query.strip()}%"
    rows = conn.execute(
        """
        SELECT * FROM movies
        WHERE title LIKE ? OR genre LIKE ? OR description LIKE ? OR tags LIKE ?
        ORDER BY rating DESC
        """,
        (keyword, keyword, keyword, keyword),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_similar_movies(movie_id):
    conn = get_connection()
    movie = conn.execute("SELECT * FROM movies WHERE id = ?", (movie_id,)).fetchone()
    if movie is None:
        conn.close()
        return []

    genres = [genre.strip() for genre in movie["genre"].split(",") if genre.strip()]
    if not genres:
        conn.close()
        return []

    genre_conditions = " OR ".join(
        "(',' || replace(genre, ', ', ',') || ',') LIKE ?" for _ in genres
    )
    rows = conn.execute(
        f"""
        SELECT * FROM movies
        WHERE ({genre_conditions}) AND id != ?
        ORDER BY rating DESC
        LIMIT 5
        """,
        tuple(f"%,{genre},%" for genre in genres) + (movie_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def movie_exists(movie_id):
    conn = get_connection()
    exists = conn.execute(
        "SELECT 1 FROM movies WHERE id = ?",
        (movie_id,),
    ).fetchone() is not None
    conn.close()
    return exists


if __name__ == "__main__":
    create_database()
    print("Database created successfully!")