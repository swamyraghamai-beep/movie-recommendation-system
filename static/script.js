function escapeHtml(value = "") {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function posterArtwork(title, genre) {
    const colors = [
        { name: "sci-fi", color: "#3186a8" },
        { name: "science fiction", color: "#3186a8" },
        { name: "action", color: "#c04b45" },
        { name: "adventure", color: "#c78336" },
        { name: "romance", color: "#b94e76" },
        { name: "comedy", color: "#c99b3f" },
        { name: "drama", color: "#567c78" },
        { name: "crime", color: "#755d9c" },
        { name: "horror", color: "#78516e" },
        { name: "animation", color: "#4f91a0" }
    ];
    const normalizedGenre = String(genre || "").toLowerCase();
    const theme = colors.find((item) => normalizedGenre.includes(item.name));
    const accent = theme ? theme.color : "#a36248";
    const titleLines = [];
    let currentLine = "";
    String(title || "Movie").split(/\s+/).forEach((word) => {
        const candidate = currentLine ? `${currentLine} ${word}` : word;
        if (candidate.length > 20 && currentLine) {
            titleLines.push(currentLine);
            currentLine = word;
        } else {
            currentLine = candidate;
        }
    });
    if (currentLine) titleLines.push(currentLine);
    if (titleLines.length > 3) {
        titleLines.length = 3;
        titleLines[2] = `${titleLines[2].slice(0, 17)}...`;
    }
    const titleMarkup = titleLines.map((line, index) =>
        `<text x="64" y="${700 + index * 48}" fill="#fff" font-family="Arial,sans-serif" font-size="38" font-weight="700">${escapeHtml(line)}</text>`
    ).join("");
    const safeGenre = escapeHtml(
        String(genre || "FEATURE FILM").split(",")[0].trim()
    );
    const svg = `
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 900">
            <defs>
                <linearGradient id="backdrop" x1="0" y1="0" x2="1" y2="1">
                    <stop stop-color="#111522"/>
                    <stop offset="1" stop-color="${accent}"/>
                </linearGradient>
                <radialGradient id="glow">
                    <stop stop-color="${accent}" stop-opacity=".85"/>
                    <stop offset="1" stop-color="${accent}" stop-opacity="0"/>
                </radialGradient>
            </defs>
            <rect width="600" height="900" fill="url(#backdrop)"/>
            <circle cx="430" cy="300" r="250" fill="url(#glow)"/>
            <path d="M0 650 600 380v520H0z" fill="#10131c" fill-opacity=".62"/>
            <path d="M0 700 600 440" stroke="#fff" stroke-opacity=".2" stroke-width="3"/>
            <rect x="38" y="40" width="524" height="820" rx="12" fill="none" stroke="#fff" stroke-opacity=".28" stroke-width="2"/>
            <text x="64" y="100" fill="#fff" fill-opacity=".82" font-family="Arial,sans-serif" font-size="20" font-weight="700" letter-spacing="5">MOVIEHUB</text>
            ${titleMarkup}
            <text x="66" y="840" fill="#fff" fill-opacity=".82" font-family="Arial,sans-serif" font-size="19" letter-spacing="3">${safeGenre.toUpperCase()}</text>
        </svg>`;
    return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

function setPosterFallbacks(container = document) {
    container.querySelectorAll(".movie-poster").forEach((poster) => {
        if (!poster.getAttribute("src")) {
            poster.src = posterArtwork(poster.dataset.title, poster.dataset.genre);
        }
        poster.addEventListener("error", () => {
            if (
                poster.dataset.tmdbPoster === "true" &&
                poster.dataset.tmdbRefresh !== "true"
            ) {
                poster.dataset.tmdbRefresh = "true";
                poster.src = `/poster/${encodeURIComponent(poster.dataset.movieId)}?refresh=1`;
                return;
            }
            if (poster.dataset.fallbackApplied !== "true") {
                poster.dataset.fallbackApplied = "true";
                poster.src = posterArtwork(poster.dataset.title, poster.dataset.genre);
            }
        }, { once: true });
    });
}

function renderMovieCards(movies) {
    if (!Array.isArray(movies) || movies.length === 0) {
        return "<p>No movies found.</p>";
    }

    const tmdbPostersEnabled = document
        .getElementById("movies")
        ?.dataset.tmdbPosters === "true";

    return movies.map((movie) => {
        const movieId = Number(movie.id);
        const posterSrc = tmdbPostersEnabled
            ? `/poster/${encodeURIComponent(movieId)}`
            : movie.poster || posterArtwork(movie.title, movie.genre);
        return `
        <article class="movie-card" data-title="${escapeHtml(movie.title)}">
            <img class="movie-poster" src="${escapeHtml(posterSrc)}" data-title="${escapeHtml(movie.title)}" data-genre="${escapeHtml(movie.genre)}" data-movie-id="${movieId}" data-tmdb-poster="${tmdbPostersEnabled ? "true" : "false"}" alt="Poster for ${escapeHtml(movie.title)}" loading="lazy">
            <h3>${escapeHtml(movie.title)}</h3>
            <p><strong>Genre:</strong> ${escapeHtml(movie.genre)}</p>
            <p>⭐ ${escapeHtml(movie.rating)}</p>
            <p>${escapeHtml(movie.description || "")}</p>
            <button type="button" class="recommend-btn" data-movie-id="${Number(movie.id)}">
                🎯 Recommend similar movies
            </button>
        </article>
    `;
    }).join("");
}

async function fetchMovies(url) {
    const response = await fetch(url, {
        headers: { "Accept": "application/json" }
    });
    const result = await response.json();

    if (!response.ok) {
        throw new Error(result.error || "The request could not be completed.");
    }

    return result;
}

async function recommend(movieId) {
    const recommendations = document.getElementById("recommendations");
    if (!recommendations || !Number.isInteger(movieId) || movieId < 1) return;

    recommendations.innerHTML = "<p>Loading recommendations...</p>";

    try {
        const movies = await fetchMovies(`/recommend/${encodeURIComponent(movieId)}`);
        recommendations.innerHTML = `
            <h2>Recommended Movies</h2>
            <div class="recommendation-list">${renderMovieCards(movies)}</div>
        `;
        setPosterFallbacks(recommendations);
        recommendations.querySelectorAll(".recommend-btn").forEach((button) => {
            button.remove();
        });
    } catch (error) {
        console.error("Recommendation request failed:", error);
        recommendations.textContent = error.message || "Unable to load recommendations.";
    }
}

async function searchMovies(query) {
    const moviesContainer = document.getElementById("movies");
    if (!moviesContainer) return;

    moviesContainer.innerHTML = "<p>Searching...</p>";

    try {
        const movies = await fetchMovies(`/search?q=${encodeURIComponent(query)}`);
        moviesContainer.innerHTML = renderMovieCards(movies);
        setPosterFallbacks(moviesContainer);
    } catch (error) {
        console.error("Movie search failed:", error);
        moviesContainer.textContent = error.message || "Unable to load movies.";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    setPosterFallbacks();

    document.querySelectorAll(".password-toggle").forEach((button) => {
        const syncPasswordButtonState = () => {
            const input = document.getElementById(button.dataset.passwordTarget);
            if (!input) return;

            const isPasswordVisible = input.type === "text";
            button.textContent = isPasswordVisible ? "🙈" : "👁";
            button.setAttribute("aria-label", isPasswordVisible ? "Hide password" : "Show password");
            button.setAttribute("aria-pressed", String(isPasswordVisible));
        };

        syncPasswordButtonState();
        button.addEventListener("click", () => {
            const input = document.getElementById(button.dataset.passwordTarget);
            if (!input) return;

            input.type = input.type === "password" ? "text" : "password";
            syncPasswordButtonState();
        });
    });

    document.querySelectorAll(".toast").forEach((toast) => {
        const dismiss = () => {
            toast.classList.add("toast-dismissed");
            window.setTimeout(() => toast.remove(), 220);
        };

        toast.querySelector(".toast-close")?.addEventListener("click", dismiss);
        if (!toast.classList.contains("toast-error")) {
            window.setTimeout(dismiss, 4500);
        }
    });

    const searchInput = document.getElementById("movie-search");
    let searchTimer;

    if (searchInput) {
        searchInput.addEventListener("input", () => {
            window.clearTimeout(searchTimer);
            searchTimer = window.setTimeout(() => {
                searchMovies(searchInput.value.trim());
            }, 200);
        });
    }

    document.addEventListener("click", (event) => {
        const button = event.target.closest(".recommend-btn");
        if (button) {
            recommend(Number(button.dataset.movieId));
        }
    });
});
