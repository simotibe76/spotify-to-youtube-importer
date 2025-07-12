import os
import json
import time
from googleapiclient.discovery import build
# from google_auth_oauthlib.flow import InstalledAppFlow # Non più necessaria
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube"]
LINKS_FILE = "youtube_links.txt"
PLAYLISTS_FILE = "Playlist1.json" # Assicurati che questo file sia caricato nel repo GitHub
FAVORITES_FILE = "YourLibrary.json" # Assicurati che questo file sia caricato nel repo GitHub

def authenticate_youtube():
    # Recupera le credenziali dai Secrets di GitHub (variabili d'ambiente)
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    refresh_token = os.environ.get('GOOGLE_REFRESH_TOKEN')

    if not all([client_id, client_secret, refresh_token]):
        print("Errore: Credenziali Google non trovate nelle variabili d'ambiente.")
        print("Assicurati di aver impostato GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET e GOOGLE_REFRESH_TOKEN come GitHub Secrets.")
        exit(1) # Esci dal processo con un errore

    # Crea un oggetto Credentials usando il refresh token
    creds = Credentials(
        token=None,  # Il token di accesso verrà generato/aggiornato
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES
    )

    # Forza un refresh del token per assicurarti che sia valido e aggiornato
    try:
        if not creds.valid or creds.expired:
            creds.refresh(Request())
        print("✅ Autenticazione YouTube riuscita.")
    except Exception as e:
        print(f"❌ Errore durante l'autenticazione o il refresh del token: {e}")
        print("Verifica che GOOGLE_REFRESH_TOKEN sia valido e che client_id/secret siano corretti.")
        exit(1) # Esci dal processo con un errore

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
        request = Youtube().list(
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
    if os.path.exists(LINKS_FILE):
        with open(LINKS_FILE, "r") as f:
            return set(line.strip() for line in f.readlines())
    return set()

def save_link(link):
    with open(LINKS_FILE, "a") as f:
        f.write(link + "\n")

def process_playlist(youtube, playlist_name, tracks, existing_links):
    print(f"\n▶ Creazione playlist: {playlist_name}")
    playlist_id = create_youtube_playlist(youtube, playlist_name)
    # Contatore per il limite giornaliero
    processed_today = 0
    MAX_DAILY_QUOTA = 30 # Il tuo limite di 30 brani al giorno

    for track in tracks:
        # Se abbiamo raggiunto il limite giornaliero, interrompi
        if processed_today >= MAX_DAILY_QUOTA:
            print(f"⚠️ Raggiunto il limite di {MAX_DAILY_QUOTA} brani per oggi. Riprenderò domani.")
            break

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
            processed_today += 1 # Incrementa il contatore solo se aggiunto
            time.sleep(1) # Rallenta le richieste per evitare sovraccarico API
        else:
            print(f"❌ Non trovato: {title}")

def main():
    print("🚀 Avvio l'importazione...")
    youtube = authenticate_youtube()
    existing_links = load_existing_links()

    # --- Importa Playlist normali ---
    with open(PLAYLISTS_FILE, "r") as f:
        playlists_data = json.load(f)

    for playlist in playlists_data["playlists"][:1]: # Rimosso [:1] per processare tutte le playlist
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
        simplified = [{"trackName": t["trackName"], "artistName": t["artistName"]} for t in favorite_tracks]
        process_playlist(youtube, "I miei preferiti di Spotify", simplified, existing_links)

if __name__ == "__main__":
    main()
