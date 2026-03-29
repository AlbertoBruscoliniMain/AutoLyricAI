# AutoLyricAI - Codice importante e moduli usati

## Struttura del progetto

I file principali del progetto sono:

- `app.py`: backend Flask e API web
- `templates/index.html`: frontend completo della web app
- `transcriber.py`: trascrizione e allineamento temporale
- `downloader.py`: download audio con `yt-dlp`
- `lyrics_fetcher.py`: ricerca lyric online
- `song_finder.py`: ricerca metadati e cover via iTunes
- `formatter.py`: salvataggio `.lrc` e gestione playlist
- `main.py`: entry point da terminale

## File piu importanti

## 1. `app.py`

E il punto di orchestrazione della versione web.

Responsabilita principali:

- espone le route Flask
- gestisce il flusso completo del brano richiesto
- scarica e salva le cover
- legge e aggiorna la playlist
- serve audio e immagini al frontend

### Route principali

- `/`
  - carica la pagina web
- `/api/process`
  - esegue la pipeline completa del brano
  - invia eventi di stato tramite SSE
- `/api/playlist`
  - restituisce i brani salvati
  - completa anche il backfill delle cover mancanti
- `/api/load`
  - ricarica segmenti e audio di un brano gia in cache
- `/api/delete`
  - elimina lyric, audio e cover di un brano
- `/api/audio/<filename>`
  - serve l'MP3
- `/api/cover/<filename>`
  - serve la cover salvata

### Funzioni chiave

- `safe_title`
  - converte un titolo in nome file sicuro
- `download_cover_file`
  - scarica l'immagine e la salva in `lyrics_output/covers`
- `ensure_entry_cover`
  - controlla se una voce playlist ha gia una cover valida
  - se manca, prova a rigenerarla

## 2. `transcriber.py`

E il modulo piu delicato del progetto.

Responsabilita principali:

- eseguire la trascrizione con Faster Whisper
- usare i word timestamps
- allineare il testo corretto ai tempi reali del brano

### Funzioni chiave

- `get_transcription`
  - punto di ingresso del modulo
  - decide se usare forced alignment oppure fallback semplice
- `_collect_whisper_words`
  - estrae parole e tempi da Whisper
- `_collect_lyric_words`
  - trasforma il testo ufficiale in una sequenza confrontabile
- `_semi_global_align`
  - esegue l'allineamento monotono tra parole lyric e parole trascritte
- `_fill_missing_times`
  - interpola i tempi mancanti tra ancore affidabili
- `_forced_align`
  - costruisce i segmenti finali riga per riga
- `_uniform`
  - fallback quando non ci sono dati abbastanza buoni

### Perche e importante

Questo modulo risolve il problema piu difficile del progetto:

- il testo corretto spesso non coincide parola per parola con la trascrizione
- i ritornelli possono ripetersi
- l'ordine va mantenuto

L'allineamento globale monotono riduce errori tipici come:

- riga evidenziata troppo presto
- ritornello agganciato alla strofa sbagliata
- compressione dei tempi in pochi secondi

## 3. `templates/index.html`

Questo file contiene sia HTML sia CSS sia JavaScript del frontend.

Responsabilita principali:

- ricevere gli eventi del backend
- costruire la playlist
- mostrare lyric e player
- sincronizzare l'interfaccia con `audio.currentTime`

### Funzioni JS rilevanti

- `doSearch`
  - apre la connessione SSE verso `/api/process`
- `loadSong`
  - carica segmenti e audio nel player
- `renderLyrics`
  - stampa le lyric sincronizzate
- `renderLyricsPreview`
  - mostra una preview del testo prima del timing finale
- `refreshPlaylist`
  - ricostruisce la sidebar
- `createPlaylistIcon`
  - mostra cover o fallback icon
- `syncLyrics`
  - sceglie la riga attiva in base al tempo corrente dell'audio

### Punto tecnico importante

Il frontend non calcola i tempi da solo.

Il browser usa solo i `start` ricevuti dal backend. Quindi la qualita del sincronismo dipende soprattutto dal lavoro fatto in `transcriber.py`.

## 4. `formatter.py`

Gestisce la persistenza locale del progetto.

Responsabilita principali:

- conversione secondi -> formato LRC
- salvataggio file `.lrc`
- aggiornamento playlist JSON
- caricamento della cache

### Funzioni chiave

- `save_as_lrc`
  - salva il testo sincronizzato in formato LRC
- `update_playlist`
  - registra file audio, cover e lyric nella playlist
- `check_cache`
  - cerca un brano gia disponibile
- `load_from_lrc`
  - rilegge il file LRC in memoria

## 5. `downloader.py`

Usa `yt-dlp` per scaricare l'audio migliore disponibile.

Responsabilita principali:

- ricerca automatica del brano
- download audio
- conversione in MP3
- raccolta thumbnail video come fallback cover

### Punto importante

Il modulo non decide i tempi delle lyric. Fornisce solo l'audio e metadati utili al resto della pipeline.

## 6. `lyrics_fetcher.py`

Serve a recuperare lyric corrette quando possibile.

Responsabilita principali:

- pulizia di titoli rumorosi
- costruzione di piu combinazioni artista/titolo
- richiesta HTTP verso `lyrics.ovh`
- rimozione di tag come `[Verse]`, `[Chorus]`

Questo migliora molto il risultato finale perche consente di allineare il testo corretto invece di affidarsi solo alla trascrizione.

## 7. `song_finder.py`

Interroga l'API iTunes per trovare:

- titolo canonico
- artista
- artwork del brano

Questo modulo e utile sia per l'interfaccia sia per migliorare la precisione delle query downstream.

## 8. `main.py`

E una versione terminale del progetto.

Rispetto alla web app:

- usa input da shell
- mostra messaggi di avanzamento testuali
- puo stampare il testo sincronizzato in console

La logica di base e la stessa, ma il coordinamento web moderno avviene in `app.py`.

## Moduli esterni usati

Le dipendenze dichiarate in `requirements.txt` sono:

- `flask`
  - framework web
  - usato per route, risposta JSON, SSE e serving file
- `yt-dlp`
  - ricerca e download audio da YouTube
- `faster-whisper`
  - trascrizione audio e word timestamps

## Moduli standard Python usati

Oltre alle dipendenze esterne, il progetto usa molto la standard library:

- `os`
  - path, directory, rename, delete file
- `json`
  - serializzazione playlist e parsing risposte API
- `urllib.request` e `urllib.parse`
  - chiamate HTTP semplici verso iTunes e lyrics.ovh
- `re`
  - pulizia titoli e parsing testo
- `mimetypes`
  - riconoscimento tipo file delle cover
- `glob`
  - ricerca di cover con stesso nome base
- `datetime`
  - timestamp di aggiunta in playlist
- `difflib`
  - similarity e scoring tra parole lyric e parole trascritte
- `statistics.median`
  - stima di un passo temporale medio tra parole
- `time`
  - usato nella versione CLI per la stampa sincronizzata

## Dati e file generati

Durante il funzionamento vengono prodotti file locali:

- `lyrics_output/*.lrc`
- `lyrics_output/audio/*.mp3`
- `lyrics_output/covers/*`
- `lyrics_output/playlist.json`

Questi file non sono codice, ma sono centrali nel comportamento dell'app.

## In sintesi

Se bisogna capire il progetto in poco tempo, l'ordine giusto di lettura e:

1. `app.py`
2. `transcriber.py`
3. `templates/index.html`
4. `formatter.py`
5. `downloader.py`
6. `lyrics_fetcher.py`
7. `song_finder.py`

Questo ordine segue il percorso reale dei dati:

- richiesta utente
- ricerca testo e audio
- trascrizione e allineamento
- salvataggio
- rendering finale nel browser
