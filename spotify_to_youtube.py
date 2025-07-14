import os
import json
import time
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube"]
LINKS_FILE = "youtube_links.txt"
PLAYLISTS_FILE = "Playlist1.json"
FAVORITES_FILE = "YourLibrary.json"

def authenticate_youtube():
    """
    Autentica l'applicazione con l'API di YouTube usando le credenziali
    fornite tramite le variabili d'ambiente (GitHub Secrets).
    """
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    refresh_token = os.environ.get('GOOGLE_REFRESH_TOKEN')

    if not all([client_id, client_secret, refresh_token]):
        print("Errore: Credenziali Google non trovate nelle variabili d'ambiente.")
        print("Assicurati di aver impostato GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET e GOOGLE_REFRESH_TOKEN come GitHub Secrets.")
        exit(1)

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES
    )

    try:
        if not creds.valid or creds.expired:
            creds.refresh(Request())
        print("✅ Autenticazione YouTube riuscita.")
    except Exception as e:
        print(f"❌ Errore durante l'autenticazione o il refresh del token: {e}")
        print("Verifica che GOOGLE_REFRESH_TOKEN sia valido e che client_id/secret siano corretti.")
        exit(1)

    return build("youtube", "v3", credentials=creds)

def get_or_create_youtube_playlist(youtube_service, playlist_name):
    """
    Cerca una playlist esistente su YouTube con il nome specificato.
    Se la trova, restituisce il suo ID. Altrimenti, crea una nuova playlist
    e restituisce il suo ID.
    """
    # 1. Cerca playlist esistente
    print(f"🔄 Cercando playlist esistente: '{playlist_name}'...")
    try:
        request = youtube_service.playlists().list(
            part="snippet",
            mine=True, # Cerca nelle playlist dell'utente autenticato
            maxResults=50 # Ottieni fino a 50 playlist per la ricerca
        )
        response = request.execute()

        for item in response.get('items', []):
            if item['snippet']['title'] == playlist_name:
                print(f"✅ Trovata playlist esistente: '{playlist_name}' (ID: {item['id']})")
                return item['id']
    except Exception as e:
        print(f"⚠️ Errore durante la ricerca della playlist '{playlist_name}': {e}")
        # Continua per tentare la creazione se la ricerca fallisce

    # 2. Se non trovata, crea nuova playlist
    print(f"🆕 Playlist '{playlist_name}' non trovata. Creazione in corso...")
    try:
        request = youtube_service.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": playlist_name,
                    "description": f"Importata da Spotify: {playlist_name}",
                },
                "status": {
                    "privacyStatus": "public" # Puoi cambiare in "unlisted" o "private" se preferisci
                }
            },
        )
        response = request.execute()
        print(f"🎉 Playlist '{playlist_name}' creata con successo (ID: {response['id']})")
        return response["id"]
    except Exception as e:
        print(f"❌ Errore durante la creazione della playlist '{playlist_name}': {e}")
        return None # Ritorna None se la creazione fallisce

def get_playlist_video_ids(youtube_service, playlist_id):
    """
    Recupera tutti gli ID dei video presenti in una data playlist.
    """
    video_ids = set()
    next_page_token = None
    while True:
        request = youtube_service.playlistItems().list(
            part="contentDetails",
            playlistId=playlist_id,
            maxResults=50, # Max risultati per pagina
            pageToken=next_page_token
        )
        response = request.execute()
        for item in response.get('items', []):
            video_ids.add(item['contentDetails']['videoId'])
        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break
    return video_ids

def search_youtube_video(youtube_service, query):
    """
    Cerca un video su YouTube basandosi su una query (titolo del brano e artista).
    Restituisce l'ID del video del primo risultato, altrimenti None.
    """
    try:
        request = youtube_service.search().list(
            part="snippet",
            maxResults=1,
            q=query,
            type="video"
        )
        response = request.execute()
        items = response.get("items", [])
        if not items:
            # print(f"Nessun risultato per '{query}'") # Commentato per ridurre il log verboso se non trova molti brani
            return None
        return items[0]["id"]["videoId"]
    except Exception as e:
        print(f"Errore nella ricerca YouTube per '{query}': {e}")
        return None

def add_video_to_playlist(youtube_service, playlist_id, video_id):
    """
    Aggiunge un video a una playlist YouTube specificata.
    """
    try:
        request = youtube_service.playlistItems().insert(
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
    except Exception as e:
        # Codice di errore 409 indica un duplicato (video già nella playlist)
        if "409" in str(e) and "playlistItemDuplicate" in str(e):
            print(f"ℹ️ Video {video_id} già presente nella playlist {playlist_id}. Saltato.")
        else:
            print(f"⚠️ Errore durante l'aggiunta del video {video_id} alla playlist {playlist_id}: {e}")

def load_existing_links():
    """
    Carica i link dei brani già importati dal file di stato.
    """
    if os.path.exists(LINKS_FILE):
        with open(LINKS_FILE, "r") as f:
            return set(line.strip() for line in f.readlines())
    return set()

def save_link(link):
    """
    Salva un link di un brano nel file di stato.
    """
    with open(LINKS_FILE, "a") as f:
        f.write(link + "\n")

def process_playlist(youtube_service, playlist_name, tracks_data, existing_links_file):
    """
    Processa una lista di brani, creandone/trovandone una playlist su YouTube
    e aggiungendo i brani, rispettando la quota giornaliera.
    """
    print(f"\n▶ Elaborazione playlist: {playlist_name}")
    
    # Ottieni o crea l'ID della playlist
    playlist_id = get_or_create_youtube_playlist(youtube_service, playlist_name)
    
    if not playlist_id:
        print(f"⚠️ Impossibile ottenere o creare la playlist '{playlist_name}'. Saltando l'elaborazione dei brani.")
        return # Esci se l'ID della playlist non è disponibile

    # Recupera gli ID dei video già presenti nella playlist YouTube
    existing_playlist_video_ids = get_playlist_video_ids(youtube_service, playlist_id)
    print(f"Trovati {len(existing_playlist_video_ids)} video già nella playlist YouTube '{playlist_name}'.")

    processed_today = 0
    MAX_DAILY_QUOTA = 30 # Il tuo limite di 30 brani al giorno

    for track_item in tracks_data:
        # Contatore per il limite giornaliero
        if processed_today >= MAX_DAILY_QUOTA:
            print(f"⚠️ Raggiunto il limite di {MAX_DAILY_QUOTA} brani per oggi per la playlist '{playlist_name}'. Riprenderò domani.")
            break

        # Determina il formato delle chiavi del brano (da Playlist1.json o YourLibrary.json)
        track_name = None
        artist_name = None

        if "trackName" in track_item and "artistName" in track_item:
            track_name = track_item["trackName"]
            artist_name = track_item["artistName"]
        elif "track" in track_item and "artist" in track_item:
            track_name = track_item["track"]
            artist_name = track_item["artist"]
        
        if not track_name or not artist_name:
            print(f"⏩ Saltato (dati brano mancanti o formato sconosciuto): {track_item}")
            continue

        title_for_file = f"{track_name} - {artist_name}" # Formato più robusto per il file di appoggio
        
        # Primo controllo: se il brano è già nel nostro file di appoggio (evita ricerche API)
        if title_for_file in existing_links_file:
            print(f"⏩ Saltato (già importato nel file di appoggio): {title_for_file}")
            continue
        
        print(f"🔍 Ricerca: {title_for_file}")
        video_id = search_youtube_video(youtube_service, title_for_file)
        
        if video_id:
            # Secondo controllo: se il video è già nella playlist YouTube
            if video_id in existing_playlist_video_ids:
                print(f"⏩ Saltato (video {video_id} già presente nella playlist YouTube '{playlist_name}'): {title_for_file}")
                save_link(title_for_file) # Salva comunque nel file di appoggio per non cercarlo più
                continue
            
            add_video_to_playlist(youtube_service, playlist_id, video_id)
            save_link(title_for_file)
            print(f"✅ Aggiunto: {title_for_file}")
            processed_today += 1
            time.sleep(1) # Rallenta le richieste per evitare sovraccarico API
        else:
            print(f"❌ Non trovato su YouTube: {title_for_file}")

def main():
    print("🚀 Avvio l'importazione...")
    youtube_service = authenticate_youtube()
    existing_links_file = load_existing_links()

    # --- Importa Playlist normali ---
    with open(PLAYLISTS_FILE, "r") as f:
        playlists_data = json.load(f)

    # Processa tutte le playlist
    for playlist in playlists_data.get("playlists", []):
        playlist_name = playlist.get("name", "Senza nome")
        items = playlist.get("items", [])
        
        tracks_to_process = [
            item["track"] for item in items 
            if item.get("track") and isinstance(item["track"], dict) and "trackName" in item["track"] and "artistName" in item["track"]
        ]
        
        if tracks_to_process:
            process_playlist(youtube_service, playlist_name, tracks_to_process, existing_links_file)
        else:
            print(f"ℹ️ Nessun brano valido trovato per la playlist '{playlist_name}'. Potrebbe contenere solo episodi o dati mancanti.")

    # --- Importa brani preferiti ---
    with open(FAVORITES_FILE, "r") as f:
        library_data = json.load(f)

    favorite_tracks_data = library_data.get("tracks", [])
    
    tracks_to_process_favorites = [
        t for t in favorite_tracks_data 
        if t.get("track") and t.get("artist")
    ]

    if tracks_to_process_favorites:
        process_playlist(youtube_service, "Brani preferiti di Spotify", tracks_to_process_favorites, existing_links_file)
    else:
        print("ℹ️ Nessun brano valido trovato in YourLibrary.json per l'importazione dei preferiti.")

    print("🎉 Importazione completata!")

if __name__ == "__main__":
    main()
