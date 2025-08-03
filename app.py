import os
import random
import json
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

PLAYER_FOLDER = os.path.join("static", "players")
PLAYER_RATINGS_FILE = "player_ratings.json"
EXCLUDED_FILE = "excluded_players.json"
RECENT_MATCHUPS_FILE = "recent_matchups.json"

INITIAL_RATING = 1400
K_FACTOR = 32

# --- Helpers for data persistence ---

def load_ratings():
    if os.path.exists(PLAYER_RATINGS_FILE):
        with open(PLAYER_RATINGS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_ratings(ratings):
    with open(PLAYER_RATINGS_FILE, "w") as f:
        json.dump(ratings, f)

def load_excluded():
    if os.path.exists(EXCLUDED_FILE):
        with open(EXCLUDED_FILE, "r") as f:
            return json.load(f)
    return {}

def save_excluded(excluded):
    with open(EXCLUDED_FILE, "w") as f:
        json.dump(excluded, f)

def load_recent_matchups():
    if os.path.exists(RECENT_MATCHUPS_FILE):
        with open(RECENT_MATCHUPS_FILE, "r") as f:
            return json.load(f)
    return []

def save_recent_matchups(recent):
    # Keep last 20 matchups max
    with open(RECENT_MATCHUPS_FILE, "w") as f:
        json.dump(recent[-20:], f)

# --- ELO rating functions ---

def expected_score(r_a, r_b):
    return 1 / (1 + 10 ** ((r_b - r_a) / 400))

def update_elo(r_winner, r_loser):
    e_winner = expected_score(r_winner, r_loser)
    e_loser = expected_score(r_loser, r_winner)

    new_winner = r_winner + K_FACTOR * (1 - e_winner)
    new_loser = r_loser + K_FACTOR * (0 - e_loser)

    return new_winner, new_loser

# --- Player selection ---

def choose_players():
    all_players = [f for f in os.listdir(PLAYER_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    ratings = load_ratings()
    excluded = load_excluded()
    recent_matchups = load_recent_matchups()

    # Filter out excluded players (excluded count > 0)
    available = [p for p in all_players if excluded.get(p, 0) == 0]

    # Fallback: if less than 2 available, reset exclusions and pick any
    if len(available) < 2:
        excluded.clear()
        save_excluded(excluded)
        available = all_players.copy()

    # Assign weights by rating (default INITIAL_RATING)
    weights = [ratings.get(p, INITIAL_RATING) for p in available]

    # Try 100 times to find two distinct players who haven't recently faced each other
    for _ in range(100):
        p1, p2 = random.choices(available, weights=weights, k=2)
        if p1 != p2 and (p1, p2) not in recent_matchups and (p2, p1) not in recent_matchups:
            recent_matchups.append((p1, p2))
            save_recent_matchups(recent_matchups)
            return p1, p2

    # If no good pair found, just pick any 2 different players
    p1, p2 = random.sample(available, 2)
    recent_matchups.append((p1, p2))
    save_recent_matchups(recent_matchups)
    return p1, p2

# --- Routes ---

@app.route("/")
def index():
    p1, p2 = choose_players()
    return render_template("index.html", player1=p1, player2=p2)

@app.route("/vote", methods=["POST"])
def vote():
    winner_key = request.form["winner"]
    # Identify winner and loser filenames
    p1 = request.form["p1"]
    p2 = request.form["p2"]
    winner = p1 if winner_key == "p1" else p2
    loser = p2 if winner_key == "p1" else p1

    ratings = load_ratings()
    excluded = load_excluded()

    # Get current ratings or default initial
    r_winner = ratings.get(winner, INITIAL_RATING)
    r_loser = ratings.get(loser, INITIAL_RATING)

    # Update ratings
    new_winner, new_loser = update_elo(r_winner, r_loser)
    ratings[winner] = new_winner
    ratings[loser] = new_loser

    # Handle consecutive wins tracking inside a separate dict
    if "consecutive_wins" not in ratings:
        ratings["consecutive_wins"] = {}

    wins = ratings["consecutive_wins"].get(winner, 0) + 1
    ratings["consecutive_wins"][winner] = wins
    ratings["consecutive_wins"][loser] = 0

    # If player hits 3 consecutive wins, exclude for next 8 rounds
    if wins >= 3:
        excluded[winner] = 8
        ratings["consecutive_wins"][winner] = 0  # reset consecutive wins after exclusion

    # Decrement exclusion counters for all except current winner (excluded counts > 0)
    for player in list(excluded.keys()):
        if player != winner and excluded[player] > 0:
            excluded[player] -= 1
            if excluded[player] <= 0:
                excluded[player] = 0

    save_ratings(ratings)
    save_excluded(excluded)

    return redirect(url_for("index"))

@app.route("/leaderboard")
def leaderboard():
    ratings = load_ratings()
    all_players = [f for f in os.listdir(PLAYER_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

    display_ratings = []
    for player in all_players:
        name = player.rsplit(".", 1)[0]
        rating = ratings.get(player, INITIAL_RATING)
        display_ratings.append((name, round(rating)))

    ranked = sorted(display_ratings, key=lambda x: x[1], reverse=True)

    return render_template("leaderboard.html", ratings=ranked)

@app.route("/reset")
def reset():
    for file in [PLAYER_RATINGS_FILE, EXCLUDED_FILE, RECENT_MATCHUPS_FILE]:
        if os.path.exists(file):
            os.remove(file)
    return "Leaderboard and data reset."

if __name__ == "__main__":
    app.run(debug=True)
