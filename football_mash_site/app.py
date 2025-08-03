import os
import random
import json
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

PLAYER_FOLDER = 'static/players'
RATING_FILE = 'ratings.json'
DEFAULT_RATING = 1400

# Elo rating calculation
def update_elo(rating1, rating2, result):
    k = 32
    expected1 = 1 / (1 + 10 ** ((rating2 - rating1) / 400))
    expected2 = 1 / (1 + 10 ** ((rating1 - rating2) / 400))
    rating1_new = rating1 + k * (result - expected1)
    rating2_new = rating2 + k * ((1 - result) - expected2)
    return round(rating1_new), round(rating2_new)

def load_ratings():
    if not os.path.exists(RATING_FILE):
        return {}
    with open(RATING_FILE, 'r') as f:
        return json.load(f)

def save_ratings(ratings):
    with open(RATING_FILE, 'w') as f:
        json.dump(ratings, f)

def get_players():
    return [f for f in os.listdir(PLAYER_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

@app.route('/')
def index():
    players = get_players()
    if len(players) < 2:
        return "Add at least 2 player images to /static/players/"
    p1, p2 = random.sample(players, 2)
    return render_template('index.html', p1=p1, p2=p2)

@app.route('/vote', methods=['POST'])
def vote():
    p1 = request.form['p1']
    p2 = request.form['p2']
    winner = request.form['winner']

    ratings = load_ratings()

    for p in [p1, p2]:
        if p not in ratings:
            ratings[p] = DEFAULT_RATING

    r1, r2 = ratings[p1], ratings[p2]
    if winner == 'p1':
        r1, r2 = update_elo(r1, r2, 1)
    else:
        r1, r2 = update_elo(r1, r2, 0)

    ratings[p1], ratings[p2] = r1, r2
    save_ratings(ratings)
    return redirect(url_for('index'))

@app.route('/leaderboard')
def leaderboard():
    ratings = load_ratings()
    sorted_ratings = sorted(ratings.items(), key=lambda x: x[1], reverse=True)

    def strip_extension(filename):
        return os.path.splitext(filename)[0].replace('_', ' ').title()

    cleaned_ratings = [(strip_extension(p), r) for p, r in sorted_ratings]
    return render_template('leaderboard.html', ratings=cleaned_ratings)

if __name__ == '__main__':
    try:
        app.run()
    except Exception as e:
        print("Server failed to start:", e)
