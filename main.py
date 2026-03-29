import os
from downloader import download_audio
from transcriber import get_transcription
from formatter import save_as_lrc, play_synchronized, update_playlist, check_cache
from lyrics_fetcher import fetch_lyrics

def main():
    print("=== AutoLyric AI ===")
    query = input("Inserisci il titolo della canzone (es: Imagine - John Lennon): ").strip()

    if not query:
        print("Errore: nessun input fornito.")
        return

    # Cache check
    print(f"\nControllo cache per: '{query}'...")
    segments = check_cache(query)

    if segments:
        print("      Testo gia' disponibile in cache, salto download e trascrizione.")
    else:
        # 1. Download
        print(f"\n[1/3] Ricerca e download audio per: '{query}'...")
        try:
            audio_path, meta = download_audio(query)
            print(f"      Audio scaricato: {os.path.basename(audio_path)}")
        except Exception as e:
            print(f"Errore durante il download: {e}")
            return

        # 2. Fetch lyrics hint + Transcription
        hint = fetch_lyrics(meta.get('artist', ''), meta.get('title', query))
        if hint:
            print("\n[2/3] Testo trovato online — trascrizione guidata in corso...")
        else:
            print("\n[2/3] Trascrizione AI in corso (potrebbe richiedere qualche minuto)...")
        try:
            segments = get_transcription(audio_path, hint_lyrics=hint)
            print(f"      Trovati {len(segments)} segmenti.")
        except Exception as e:
            print(f"Errore durante la trascrizione: {e}")
            os.remove(audio_path)
            return

        # 3. Save .lrc + audio
        print("\n[3/3] Generazione file .lrc...")
        try:
            lrc_path = save_as_lrc(segments, query)
            print(f"      File salvato: {lrc_path}")

            audio_dir = os.path.join(os.path.dirname(__file__), "lyrics_output", "audio")
            os.makedirs(audio_dir, exist_ok=True)
            safe = "".join(c if c.isalnum() or c in " -_()" else "_" for c in query)
            final_audio = os.path.join(audio_dir, f"{safe}.mp3")
            os.replace(audio_path, final_audio)

            playlist_path = update_playlist(query, lrc_path, f"{safe}.mp3")
            print(f"      Playlist aggiornata: {playlist_path}")
        except Exception as e:
            print(f"Errore durante il salvataggio: {e}")
            if os.path.exists(audio_path):
                os.remove(audio_path)

    print("\nFatto! Il tuo file .lrc e' pronto.")

    print("\nVuoi vedere il testo sincronizzato? (s/n): ", end="")
    if input().strip().lower() == "s":
        print("\nAvvia la canzone ora, poi premi INVIO...")
        input()
        play_synchronized(segments, query)

if __name__ == "__main__":
    main()
