import os
import json
import time
from googleapiclient.discovery import build
# Rimosse le importazioni non più necessarie per l'autenticazione locale
# from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube"]
LINKS_FILE = "youtube_links.txt"
PLAYLISTS_FILE = "Playlist1.json"
FAVORITES_FILE = "YourLibrary.json"

def authenticate_youtube():
    # Recupera le credenziali dai Secrets di GitHub (variabili d'ambiente)
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    refresh_token = os.environ.get('GOOGLE_REFRESH_TOKEN')

    # Verifica che tutte le credenziali necessarie siano presenti
    if not all([client_id, client_secret, refresh_token]):
        print("Errore: Credenziali Google non trovate nelle variabili d'ambiente.")
        print("Assicurati di aver impostato GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET e GOOGLE_REFRESH_TOKEN come GitHub Secrets.")
        exit(1) # Termina lo script con un codice di errore

    # Crea un oggetto Credentials usando il refresh token
    # Non è più necessario leggere da token.json o client_secret.json
    creds = Credentials(
        token=None,  # Il token di accesso verrà generato/aggiornato automaticamente
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
        exit(1) # Termina lo script con un codice di errore

    return build("youtube", "v3", credentials=creds)

def create_youtube_playlist(youtube_service, playlist_name):
    # La funzione ora accetta 'youtube_service' come parametro per chiarezza
    request = youtube_service.playlists().insert(
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

def search_youtube_video(youtube_service, query):
    # La funzione ora accetta 'youtube_service' come parametro per chiarezza
    try:
        request = youtube_service.search().list( # Usa youtube_service qui
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

def add_video_to_playlist(youtube_service, playlist_id, video_id):
    # La funzione ora accetta 'youtube_service' come parametro per chiarezza
    request = youtube_service.playlistItems().insert( # Usa youtube_service qui
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
            return set(line.strip() for line in f.readlines())
    return set()

def save_link(link):
    with open(LINKS_FILE, "a") as f:
        f.write(link + "\n")

def process_playlist(youtube_service, playlist_name, tracks, existing_links):
    print(f"\n▶ Creazione playlist: {playlist_name}")
    try:
        playlist_id = create_youtube_playlist(youtube_service, playlist_name)
    except Exception as e:
        print(f"⚠️ Errore durante la creazione della playlist '{playlist_name}': {e}")
        return # Esci dalla funzione se la playlist non può essere creata

    # Contatore per il limite giornaliero
    processed_today = 0
    MAX_DAILY_QUOTA = 30 # Il tuo limite di 30 brani al giorno

    for track in tracks:
        # Se abbiamo raggiunto il limite giornaliero, interrompi
        if processed_today >= MAX_DAILY_QUOTA:
            print(f"⚠️ Raggiunto il limite di {MAX_DAILY_QUOTA} brani per oggi per la playlist '{playlist_name}'. Riprenderò domani.")
            break

        # Usa le chiavi corrette 'track' e 'artist' dal tuo YourLibrary.json
        # Aggiunto un controllo per evitare KeyError se le chiavi non esistono
        track_name = track.get('track')
        artist_name = track.get('artist')

        if not track_name or not artist_name:
            print(f"⏩ Saltato (dati mancanti): {track}. Richiede 'track' e 'artist'.")
            continue

        title = f"{track_name} {artist_name}"
        
        if title in existing_links:
            print(f"⏩ Saltato (già importato): {title}")
            continue
        
        print(f"🔍 Ricerca: {title}")
        video_id = search_youtube_video(youtube_service, title) # Passa youtube_service
        
        if video_id:
            add_video_to_playlist(youtube_service, playlist_id, video_id) # Passa youtube_service
            save_link(title)
            print(f"✅ Aggiunto: {title}")
            processed_today += 1 # Incrementa il contatore solo se aggiunto
            time.sleep(1) # Rallenta le richieste per evitare sovraccarico API
        else:
            print(f"❌ Non trovato: {title}")

def main():
    print("🚀 Avvio l'importazione...")
    youtube_service = authenticate_youtube() # Ottieni l'oggetto servizio YouTube qui
    existing_links = load_existing_links()

    # --- Importa Playlist normali ---
    with open(PLAYLISTS_FILE, "r") as f:
        playlists_data = json.load(f)

    # Ho reimpostato il ciclo per processare tutte le playlist
    # Se vuoi limitare a una sola per il test, rimetti [:1]
    for playlist in playlists_data["playlists"]: 
        playlist_name = playlist.get("name", "Senza nome")
        items = playlist.get("items", [])
        # Filtra solo gli elementi che sono tracce e hanno la chiave 'track'
        tracks = [item["track"] for item in items if item.get("track") and "track" in item["track"] and "artist" in item["track"]]
        if tracks:
            # Passa l'oggetto servizio YouTube alla funzione process_playlist
            process_playlist(youtube_service, playlist_name, tracks, existing_links)

    # --- Importa brani preferiti ---
    with open(FAVORITES_FILE, "r") as f:
        library_data = json.load(f)

    favorite_tracks = library_data.get("tracks", [])
    if favorite_tracks:
        # Corretto l'accesso alle chiavi 'track' e 'artist'
        # Aggiunto un filtro per assicurarsi che ci siano le chiavi necessarie
        simplified = [
            {"track": t.get("track"), "artist": t.get("artist")} 
            for t in favorite_tracks 
            if t.get("track") and t.get("artist")
        ]
        if simplified: # Solo se ci sono brani validi
            # Passa l'oggetto servizio YouTube alla funzione process_playlist
            process_playlist(youtube_service, "Brani preferiti di Spotify", simplified, existing_links)
        else:
            print("Nessun brano valido trovato in YourLibrary.json per l'importazione.")

    print("🎉 Importazione completata!")

if __name__ == "__main__":
    main()
