
import os
import json
import time
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube"]
LINKS_FILE = "youtube_links.txt"
PLAYLISTS_FILE = "Playlist1.json"
FAVORITES_FILE = "YourLibrary.json"

def authenticate_youtube():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
            creds = flow.run_local_server(port=8080)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

def create_youtube_playlist(youtube, playlist_name):
    request = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": playlist_name,
                "description": f"Importata da Spotify: {playlist_name}",
            },
            "status": {
                "privacyStatus": "public"
            }
        },
    )
    response = request.execute()
    return response["id"]

def search_youtube_video(youtube, query):
    try:
        request = youtube.search().list(
            part="snippet",
            maxResults=1,
            q=query,
            type="video"
        )
        response = request.execute()
        items = response.get("items", [])
        if not items:
            print(f"Nessun risultato per '{query}'")
            return None
        return items[0]["id"]["videoId"]
    except Exception as e:
        print(f"Errore nella ricerca YouTube per '{query}': {e}")
        return None

def add_video_to_playlist(youtube, playlist_id, video_id):
    request = youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id
                }
            }
        },
    )
    request.execute()

def load_existing_links():
    if os.path.exists("youtube_links.txt"):
        with open("youtube_links.txt", "r") as f:
            return set(line.strip() for line in f.readlines())
    return set()

def save_link(link):
    with open("youtube_links.txt", "a") as f:
        f.write(link + "\n")

def process_playlist(youtube, playlist_name, tracks, existing_links):
    print(f"\n▶ Creazione playlist: {playlist_name}")
    playlist_id = create_youtube_playlist(youtube, playlist_name)
    for track in tracks:
        title = f"{track['trackName']} {track['artistName']}"
        if title in existing_links:
            print(f"⏩ Saltato (già importato): {title}")
            continue
        print(f"🔍 Ricerca: {title}")
        video_id = search_youtube_video(youtube, title)
        if video_id:
            add_video_to_playlist(youtube, playlist_id, video_id)
            save_link(title)
            print(f"✅ Aggiunto: {title}")
            time.sleep(1)
        else:
            print(f"❌ Non trovato: {title}")

def main():
    print("🚀 Avvio l'importazione...")
    youtube = authenticate_youtube()
    existing_links = load_existing_links()

    # Playlist1
    with open(PLAYLISTS_FILE, "r") as f:
        playlists_data = json.load(f)

    for playlist in playlists_data.get("playlists", []):
        playlist_name = playlist.get("name", "Senza nome")
        items = playlist.get("items", [])
        tracks = [item["track"] for item in items if item.get("track")]
        if tracks:
            process_playlist(youtube, playlist_name, tracks, existing_links)

    # YourLibrary
    with open(FAVORITES_FILE, "r") as f:
        library_data = json.load(f)

    favorite_tracks = library_data.get("tracks", [])
    if favorite_tracks:
        simplified = [{"trackName": t["trackName"], "artistName": t["artistName"]} for t in favorite_tracks]
        process_playlist(youtube, "I miei preferiti di Spotify", simplified, existing_links)

if __name__ == "__main__":
    main()
