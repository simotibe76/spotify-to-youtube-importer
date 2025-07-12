import os
import json
import time
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Non useremo più client_secret.json e token.json in modo diretto nel cloud
# I SCOPES rimangono gli stessi
SCOPES = ["https://www.googleapis.com/auth/youtube"]
LINKS_FILE = "youtube_links.txt"
PLAYLISTS_FILE = "Playlist1.json"
FAVORITES_FILE = "YourLibrary.json"

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

# Il resto del tuo script (create_youtube_playlist, search_youtube_video, add_video_to_playlist,
# load_existing_links, save_link, process_playlist, main) rimane invariato.

# Assicurati che le parti del tuo script che gestiscono FILES_FILE (youtube_links.txt)
# siano robusto nel leggere/scrivere.
