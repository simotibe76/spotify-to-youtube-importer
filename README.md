# Spotify to YouTube Importer 🎶➡️📺

Uno script Python per importare automaticamente le tue playlist di Spotify su YouTube.

## 🔧 Requisiti

- Python 3.8+
- Un file `client_secret.json` generato da Google Cloud Console
- Le playlist esportate da Spotify (`Playlist1.json` e `YourLibrary.json`)

## 📦 Setup

```bash
# Clona il progetto
git clone https://github.com/simotibe76/spotify-to-youtube-importer.git
cd spotify-to-youtube-importer

# Crea l'ambiente virtuale
python3 -m venv ytvenv
source ytvenv/bin/activate

# Installa le dipendenze
pip install -r requirements.txt

# Avvia lo script
python spotify_to_youtube.py
