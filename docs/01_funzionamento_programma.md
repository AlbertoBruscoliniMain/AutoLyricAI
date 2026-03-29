# AutoLyricAI - Funzionamento del programma

## Obiettivo

AutoLyricAI prende in input il nome di una canzone, scarica l'audio, recupera il testo corretto quando possibile, calcola i tempi del brano e genera un testo sincronizzato riga per riga.

Il progetto puo essere usato in due modi:

- interfaccia web Flask, tramite `app.py`
- esecuzione da terminale, tramite `main.py`

## Flusso generale

Il flusso principale e questo:

1. l'utente inserisce una query come `Imagine - John Lennon`
2. il programma controlla se il brano esiste gia in cache
3. se non esiste, cerca titolo e artista corretti
4. prova a recuperare il testo ufficiale online
5. scarica l'audio del brano
6. trascrive l'audio con Whisper
7. se il testo ufficiale esiste, allinea le lyric corrette ai tempi della musica
8. salva il risultato in `.lrc`
9. salva audio, cover e metadati nella playlist locale
10. il frontend mostra playlist, player audio e highlight sincronizzato

## Ingresso dati

### Modalita web

La route `/api/process` riceve la query, avvia il processo e invia aggiornamenti al browser tramite Server-Sent Events.

Questo permette al frontend di mostrare stato, avanzamento e risultato finale senza ricaricare la pagina.

### Modalita CLI

`main.py` legge la query da terminale, lancia lo stesso flusso logico e alla fine puo anche stampare il testo in tempo reale.

## Cache locale

Prima di fare download e trascrizione, il programma controlla se il brano e gia stato elaborato.

La cache si basa su:

- file `.lrc` in `lyrics_output/`
- metadati in `lyrics_output/playlist.json`

Se il brano e gia presente:

- non viene riscaricato l'audio
- non viene rilanciata la trascrizione
- vengono caricati direttamente segmenti e file audio gia salvati

## Ricerca metadati del brano

Il modulo `song_finder.py` usa la Search API di iTunes per ottenere:

- titolo canonico del brano
- artista corretto
- URL dell'artwork

Questo passaggio serve a normalizzare le query dell'utente e ad avere dati piu puliti per:

- ricerca lyric
- nome da mostrare in interfaccia
- cover del brano

## Recupero del testo

Il modulo `lyrics_fetcher.py` prova a ottenere il testo tramite `lyrics.ovh`.

Prima pulisce titolo e artista rimuovendo parti tipiche dei titoli YouTube, per esempio:

- `Official Video`
- `Lyrics`
- `feat.`
- `Remaster`

Se il testo viene trovato:

- il frontend mostra subito una preview delle lyric
- il backend usa quel testo come guida per l'allineamento temporale

Se il testo non viene trovato:

- il sistema ricade sulla sola trascrizione AI

## Download dell'audio

Il modulo `downloader.py` usa `yt-dlp` per cercare il miglior audio disponibile e convertirlo in MP3.

Durante questo passaggio vengono anche raccolti alcuni metadati:

- titolo
- artista
- thumbnail del video, usata come fallback se la cover iTunes manca

I file temporanei vengono scaricati in `temp_audio/`.

## Trascrizione e sincronizzazione

Il cuore tecnico del progetto e `transcriber.py`.

### Caso 1: testo ufficiale disponibile

Quando il testo corretto e disponibile:

- Faster Whisper trascrive l'audio con `word_timestamps=True`
- il codice costruisce una sequenza di parole del testo
- costruisce anche una sequenza di parole trascritte da Whisper
- esegue un allineamento globale e monotono tra le due sequenze

Questo approccio e importante perche:

- evita che ritornelli simili vengano agganciati al punto sbagliato
- mantiene l'ordine reale del brano
- produce start time molto piu vicini alla musica reale

Il risultato finale e una lista di segmenti del tipo:

```python
{"start": 42.71, "end": 44.28, "text": "You're early"}
```

### Caso 2: testo ufficiale assente

Se non c'e un testo affidabile:

- il sistema usa direttamente i segmenti trascritti da Whisper
- ogni segmento contiene testo e timestamp derivati dalla trascrizione

### Nota importante sul timing

Il progetto non usa il `vad_filter` durante la trascrizione musicale.

Questo e voluto: il Voice Activity Detection e utile per parlato e pause nette, ma sui brani musicali puo comprimere la timeline e spostare i tempi in modo errato.

## Salvataggio output

Alla fine dell'elaborazione il programma salva:

- file `.lrc` con timestamp in `lyrics_output/`
- file audio MP3 in `lyrics_output/audio/`
- cover in `lyrics_output/covers/`
- voce playlist in `lyrics_output/playlist.json`

La playlist tiene traccia di:

- titolo
- file `.lrc`
- data di aggiunta
- file audio
- file cover

## Frontend e player

La pagina `templates/index.html` gestisce:

- barra di ricerca
- playlist laterale
- player audio HTML5
- visualizzazione lyric
- highlight automatico della riga attiva

Il sincronismo lato browser funziona cosi:

1. l'audio aggiorna `currentTime`
2. il frontend trova l'ultimo segmento con `start <= currentTime`
3. quella riga diventa `active`
4. le righe precedenti diventano `past`
5. la vista scrolla verso la riga attiva

## Cover dei brani

Quando possibile il sistema scarica e salva una cover locale.

La priorita e:

1. artwork trovato via iTunes
2. thumbnail trovata nel download YouTube
3. fallback grafico con il simbolo musicale, se nessuna immagine e disponibile

Le cover vengono servite dalla route `/api/cover/<filename>`.

## Riassunto finale

AutoLyricAI non si limita a trascrivere audio: cerca di combinare metadati, lyric corrette, trascrizione AI e sincronizzazione frontend per ottenere un'esperienza simile a un karaoke line-by-line.

In breve:

- `song_finder.py` trova il brano giusto
- `lyrics_fetcher.py` cerca il testo corretto
- `downloader.py` scarica audio e thumbnail
- `transcriber.py` costruisce i tempi reali
- `formatter.py` salva file e playlist
- `app.py` espone tutto alla web app
- `index.html` mostra e sincronizza il risultato
