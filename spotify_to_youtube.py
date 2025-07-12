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
    request = Youtube().list(
        part="snippet",
        q=query,
        type="video",
        maxResults=1
    )
    response = request.execute()
    if response["items"]:
        return response["items"][0]["id"]["videoId"]
    return None

def add_video_to_playlist(youtube, playlist_id, video_id):
    request = youtube.playlistitems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id
                }
            }
        }
    )
    request.execute()

def load_existing_links():
    if os.path.exists(LINKS_FILE):
        with open(LINKS_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_link(title):
    with open(LINKS_FILE, "a") as f:
        f.write(title + "\n")

def process_playlist(youtube, playlist_name, tracks, existing_links):
    print(f"🔄 Elaborazione playlist: {playlist_name}")
    try:
        playlist_id = create_youtube_playlist(youtube, playlist_name)
    except Exception as e:
        print(f"⚠️ Errore durante la creazione della playlist {playlist_name}: {e}")
        return

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

    # --- Importa Playlist normali ---
    with open(PLAYLISTS_FILE, "r") as f:
        playlists_data = json.load(f)

    for playlist in playlists_data["playlists"][:1]:  # Rimuovi [:1] per tutte
        playlist_name = playlist.get("name", "Senza nome")
        items = playlist.get("items", [])
        tracks = [item["track"] for item in items if item.get("track")]
        if tracks:
            process_playlist(youtube, playlist_name, tracks, existing_links)

    # --- Importa brani preferiti ---
    with open(FAVORITES_FILE, "r") as f:
        library_data = json.load(f)

    favorite_tracks = library_data.get("tracks", [])
    if favorite_tracks:
        simplified = [{"trackName": t["track"], "artistName": t["artist"]} for t in favorite_tracks]
        process_playlist(youtube, "Brani preferiti di Spotify", simplified, existing_links)

    print("🎉 Importazione completata!")

if __name__ == "__main__":
    main()
