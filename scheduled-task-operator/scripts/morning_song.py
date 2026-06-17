import os
import random
import subprocess
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Read credentials from environment variables (injected by k8s Secret)
CLIENT_ID = os.environ["SPOTIFY_CLIENT_ID"]
CLIENT_SECRET = os.environ["SPOTIFY_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["SPOTIFY_REFRESH_TOKEN"]

auth_manager = SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri="http://127.0.0.1:8888/callback",
    scope="user-top-read"
)

# Inject the refresh token directly so no browser auth is needed
token_info = auth_manager.refresh_access_token(REFRESH_TOKEN)
sp = spotipy.Spotify(auth=token_info["access_token"])

# Fetch top 50 tracks and pick one at random
top_tracks = sp.current_user_top_tracks(limit=50, time_range="medium_term")
track = random.choice(top_tracks["items"])

name = track["name"]
artist = track["artists"][0]["name"]
url = track["external_urls"]["spotify"]

print(f"🎵 Morning song: {name} — {artist}")
print(f"🔗 {url}")

# Fire a macOS notification
subprocess.run([
    "osascript", "-e",
    f'display notification "🎵 {name} — {artist}" with title "Your Morning Song" subtitle "{url}"'
])