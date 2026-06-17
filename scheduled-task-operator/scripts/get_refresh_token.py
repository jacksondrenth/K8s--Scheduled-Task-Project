import spotipy
from spotipy.oauth2 import SpotifyOAuth

from config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

auth_manager = SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope="user-top-read"
)

sp = spotipy.Spotify(auth_manager=auth_manager)
top_tracks = sp.current_user_top_tracks(limit=5)

print("\n--- Your refresh token ---")
token_info = auth_manager.get_cached_token()
print(token_info['refresh_token'])

print("\n--- Sample top tracks ---")
for i, track in enumerate(top_tracks['items']):
    print(f"{i+1}. {track['name']} — {track['artists'][0]['name']}")