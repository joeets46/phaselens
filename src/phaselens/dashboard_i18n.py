"""Interface text of the local dashboard in English, Turkish, and German.

Standard library only. The wording follows common football usage in each
language rather than a word-for-word translation. Team and player names
are shown as the source records them. Event-type and position names are
shown translated; the source name is kept for matching and in the
technical details. Every text exists in every language with the same
placeholders; a test checks this.
"""

LANGUAGES = {"en": "English", "tr": "Türkçe", "de": "Deutsch"}
DEFAULT_LANGUAGE = "en"

TEXT = {
    # --- frame of the page ---
    "subtitle": {
        "en": "Pressing and 360° snapshots · StatsBomb Open Data",
        "tr": "Pres ve 360° anlık görüntüler · StatsBomb Open Data",
        "de": "Pressing und 360°-Momentaufnahmen · StatsBomb Open Data",
    },
    "view": {"en": "View", "tr": "Görünüm", "de": "Ansicht"},
    "view_overview": {"en": "Match overview", "tr": "Maç özeti", "de": "Spielübersicht"},
    "view_explorer": {"en": "360° moments", "tr": "360° anlar", "de": "360°-Momente"},
    "language": {"en": "Language", "tr": "Dil", "de": "Sprache"},
    "reload": {
        "en": "Reload and re-verify the data on disk",
        "tr": "Diskteki veriyi yeniden yükle ve doğrula",
        "de": "Daten von der Festplatte neu laden und prüfen",
    },
    "guide": {"en": "Guide", "tr": "Rehber", "de": "Hilfe"},
    "guide_title": {
        "en": "How to use PhaseLens", "tr": "PhaseLens nasıl kullanılır", "de": "So funktioniert PhaseLens",
    },
    "guide_tab_use": {"en": "Getting started", "tr": "Başlarken", "de": "Erste Schritte"},
    "guide_tab_pitch": {"en": "Reading the pitch", "tr": "Saha nasıl okunur", "de": "Das Spielfeld lesen"},
    "guide_tab_terms": {"en": "Terms", "tr": "Terimler", "de": "Begriffe"},
    "loading_overview": {
        "en": "Checking the five pilot matches…",
        "tr": "Beş pilot maç doğrulanıyor…",
        "de": "Die fünf Pilotspiele werden geprüft…",
    },
    "loading_explorer": {
        "en": "Checking the final's actions and 360° snapshots…",
        "tr": "Finalin aksiyonları ve 360° görüntüleri doğrulanıyor…",
        "de": "Aktionen und 360°-Aufnahmen des Finales werden geprüft…",
    },
    "wrong_root": {
        "en": "Start the dashboard from the PhaseLens project folder.",
        "tr": "Paneli PhaseLens proje klasöründen başlatın.",
        "de": "Starten Sie das Dashboard im PhaseLens-Projektordner.",
    },
    "error_title": {
        "en": "The data could not be loaded and verified.",
        "tr": "Veri yüklenemedi ve doğrulanamadı.",
        "de": "Die Daten konnten nicht geladen und geprüft werden.",
    },
    "error_command": {
        "en": "Run this in the project folder, then reload: {command}",
        "tr": "Bunu proje klasöründe çalıştırın, ardından yeniden yükleyin: {command}",
        "de": "Im Projektordner ausführen, dann neu laden: {command}",
    },
    "error_details": {"en": "Technical details", "tr": "Teknik ayrıntılar", "de": "Technische Details"},
    "footer": {
        "en": "Data: StatsBomb Open Data (commit {commit}…), match {match}. Read from this computer only; "
              "nothing is downloaded or changed.",
        "tr": "Veri: StatsBomb Open Data (commit {commit}…), maç {match}. Yalnızca bu bilgisayardan okunur; "
              "hiçbir şey indirilmez veya değiştirilmez.",
        "de": "Daten: StatsBomb Open Data (Commit {commit}…), Spiel {match}. Nur von diesem Rechner gelesen; "
              "nichts wird heruntergeladen oder verändert.",
    },
    # --- overview ---
    "match": {"en": "Match", "tr": "Maç", "de": "Spiel"},
    "score_note": {
        "en": "Score as recorded in the source match list.",
        "tr": "Skor, kaynaktaki maç listesinde kayıtlı olduğu gibidir.",
        "de": "Ergebnis wie in der Spielliste der Quelle erfasst.",
    },
    "home": {"en": "Home", "tr": "Ev sahibi", "de": "Heim"},
    "away": {"en": "Away", "tr": "Deplasman", "de": "Gast"},
    "team_comparison": {"en": "Team comparison", "tr": "Takım karşılaştırması", "de": "Teamvergleich"},
    "comparison_note": {
        "en": "Each bar is the team's share of the two teams' total in that row. Raw event counts: not "
              "normalized for playing time, number of matches, or opportunities, and not ratings.",
        "tr": "Her çubuk, o satırdaki iki takım toplamı içinde takımın payıdır. Ham aksiyon sayılarıdır: "
              "oynanan süreye, maç sayısına veya fırsatlara göre normalize edilmemiştir ve performans puanı "
              "değildir.",
        "de": "Jeder Balken ist der Anteil des Teams an der Summe beider Teams in dieser Zeile. Reine "
              "Ereigniszählungen: nicht nach Spielzeit, Spielanzahl oder Gelegenheiten normiert und keine "
              "Bewertung.",
    },
    "player_rows": {"en": "Players in this match", "tr": "Bu maçtaki oyuncular", "de": "Spieler in diesem Spiel"},
    "player_rows_note": {
        "en": "Sorted by team id, then player id. The order is not a ranking. CP: counter-press. Point at a "
              "column header for its definition.",
        "tr": "Takım ID'sine, ardından oyuncu ID'sine göre sıralıdır. Bu sıra bir başarı sıralaması değildir. "
              "KP: karşı pres. Tanım için imleci sütun başlığının üzerine getirin.",
        "de": "Sortiert nach Team-ID, dann Spieler-ID. Die Reihenfolge ist keine Rangliste. GP: Gegenpressing. "
              "Für die Definition mit der Maus auf eine Spaltenüberschrift zeigen.",
    },
    "col_team": {"en": "Team", "tr": "Takım", "de": "Team"},
    "col_player": {"en": "Player", "tr": "Oyuncu", "de": "Spieler"},
    "col_team_id": {"en": "Team ID", "tr": "Takım ID", "de": "Team-ID"},
    "col_player_id": {"en": "Player ID", "tr": "Oyuncu ID", "de": "Spieler-ID"},
    "metric_pressure_event_count": {
        "en": "Pressure events", "tr": "Pres aksiyonları", "de": "Pressingaktionen",
    },
    "metric_counterpress_pressure_event_count": {
        "en": "Pressure events marked as counter-press",
        "tr": "Karşı pres olarak işaretlenen presler",
        "de": "Pressingaktionen mit Gegenpressing-Markierung",
    },
    "metric_counterpress_flagged_event_count": {
        "en": "Counterpress-flagged events — supported types",
        "tr": "Karşı pres işaretli aksiyonlar — desteklenen türler",
        "de": "Aktionen mit Gegenpressing-Markierung — unterstützte Typen",
    },
    # Short table headers; the full definition is the column's tooltip.
    "short_pressure_event_count": {"en": "Pressures", "tr": "Pres", "de": "Pressing"},
    "short_counterpress_pressure_event_count": {"en": "CP pressures", "tr": "KP pres", "de": "GP-Pressing"},
    "short_counterpress_flagged_event_count": {"en": "CP events", "tr": "KP aksiyon", "de": "GP-Aktionen"},
    "help_pressure_event_count": {
        "en": "Pressure events: the provider's Pressure type recorded for this player. Raw count, not a rating.",
        "tr": "Pres aksiyonları: sağlayıcının bu oyuncu için kaydettiği Pres türü. Ham sayı, performans puanı "
              "değildir.",
        "de": "Pressingaktionen: der für diesen Spieler erfasste Pressure-Typ des Anbieters. Reine Zählung, keine "
              "Bewertung.",
    },
    "help_counterpress_pressure_event_count": {
        "en": "Pressure events marked as counter-press: pressures carrying the provider's counter-press marker "
              "(within 5 seconds of an open-play turnover). Raw count, not a rating.",
        "tr": "Karşı pres olarak işaretlenen presler: sağlayıcının karşı pres işaretini taşıyan presler (açık "
              "oyunda top kaybından sonraki 5 saniye içinde). Ham sayı, performans puanı değildir.",
        "de": "Pressingaktionen mit Gegenpressing-Markierung: Pressingaktionen mit der Gegenpressing-Markierung des "
              "Anbieters (innerhalb von 5 Sekunden nach einem Ballverlust im laufenden Spiel). Reine Zählung, keine "
              "Bewertung.",
    },
    "help_counterpress_flagged_event_count": {
        "en": "Counterpress-flagged events — supported types: actions of the seven supported types carrying the "
              "counter-press marker, offensive fouls excluded. Raw count, not a rating.",
        "tr": "Karşı pres işaretli aksiyonlar — desteklenen türler: karşı pres işaretini taşıyan, desteklenen yedi "
              "türdeki aksiyonlar; hücum faulleri hariç. Ham sayı, performans puanı değildir.",
        "de": "Aktionen mit Gegenpressing-Markierung — unterstützte Typen: Aktionen der sieben unterstützten Typen "
              "mit Gegenpressing-Markierung, ohne Offensivfouls. Reine Zählung, keine Bewertung.",
    },
    # --- explorer: filters ---
    "filters": {"en": "Find an action", "tr": "Aksiyon bul", "de": "Aktion finden"},
    "all_types": {"en": "All actions", "tr": "Tüm aksiyonlar", "de": "Alle Aktionen"},
    "all_teams": {"en": "Both teams", "tr": "İki takım", "de": "Beide Teams"},
    "all_players": {"en": "All players", "tr": "Tüm oyuncular", "de": "Alle Spieler"},
    "event_type": {"en": "Action type", "tr": "Aksiyon türü", "de": "Aktionstyp"},
    "event_team": {"en": "Team", "tr": "Takım", "de": "Team"},
    "event_player": {"en": "Player", "tr": "Oyuncu", "de": "Spieler"},
    "event_pick": {
        "en": "Action · {count} found, in match order",
        "tr": "Aksiyon · {count} sonuç, maç sırasıyla",
        "de": "Aktion · {count} Treffer, in Spielreihenfolge",
    },
    "event_prev": {"en": "Previous action", "tr": "Önceki aksiyon", "de": "Vorherige Aktion"},
    "event_next": {"en": "Next action", "tr": "Sonraki aksiyon", "de": "Nächste Aktion"},
    "no_events": {
        "en": "No actions match these filters. Change a filter to see actions.",
        "tr": "Bu filtrelere uyan aksiyon yok. Aksiyonları görmek için bir filtreyi değiştirin.",
        "de": "Keine Aktionen passen zu diesen Filtern. Ändern Sie einen Filter.",
    },
    "toggle_radii": {
        "en": "Distance rings · 5, 10, 20 units",
        "tr": "Mesafe halkaları · 5, 10, 20 birim",
        "de": "Abstandsringe · 5, 10, 20 Einheiten",
    },
    "toggle_area": {"en": "Camera view", "tr": "Kamera görüntüsü", "de": "Kamerabild"},
    "event_label": {
        "en": "{time} · {half} · {type} · {player}",
        "tr": "{time} · {half} · {type} · {player}",
        "de": "{time} · {half} · {type} · {player}",
    },
    "no_player": {"en": "no player", "tr": "oyuncu yok", "de": "kein Spieler"},
    "half_1": {"en": "1st half", "tr": "1. yarı", "de": "1. Halbzeit"},
    "half_2": {"en": "2nd half", "tr": "2. yarı", "de": "2. Halbzeit"},
    "period_n": {"en": "period {period}", "tr": "{period}. periyot", "de": "Periode {period}"},
    "started": {"en": "Starting XI", "tr": "İlk 11", "de": "Startelf"},
    "sub_on": {"en": "on {time}", "tr": "{time} girdi", "de": "eingewechselt {time}"},
    "sub_off": {"en": "off {time}", "tr": "{time} çıktı", "de": "ausgewechselt {time}"},
    "no_position": {"en": "position not recorded", "tr": "mevki kayıtlı değil", "de": "Position nicht erfasst"},
    # --- explorer: pitch and panels ---
    "pitch_title": {"en": "360° snapshot", "tr": "360° anlık görüntü", "de": "360°-Momentaufnahme"},
    "pitch_note": {
        "en": "Only players visible in the picture are drawn; units are grid units, not metres.",
        "tr": "Yalnızca görüntüde görünen oyuncular çizilir; birimler ızgara birimidir, metre değildir.",
        "de": "Nur im Bild sichtbare Spieler sind gezeichnet; Rastereinheiten, keine Meter.",
    },
    "area_note": {
        "en": "The camera view is the area recorded by the provider, not checked here.",
        "tr": "Kamera görüntüsü sağlayıcının kaydettiği alandır; burada doğrulanmamıştır.",
        "de": "Das Kamerabild ist die vom Anbieter erfasste Fläche; hier nicht geprüft.",
    },
    # Legend: one short line under the pitch; the Guide explains each symbol in full.
    "lg_actor": {
        "en": "Player who performed this action",
        "tr": "Aksiyonu yapan oyuncu",
        "de": "Spieler, der die Aktion ausführt",
    },
    "lg_teammates": {"en": "{team} — teammates", "tr": "{team} — takım arkadaşları", "de": "{team} – Mitspieler"},
    "lg_opponents": {"en": "{team} — opponents", "tr": "{team} — rakipler", "de": "{team} – Gegenspieler"},
    "lg_unknown": {
        "en": "Team marker missing", "tr": "Takım işareti eksik", "de": "Teamkennzeichen fehlt",
    },
    "lg_keeper": {"en": "Goalkeeper", "tr": "Kaleci", "de": "Torwart"},
    "lg_event_location": {"en": "Action spot", "tr": "Aksiyon noktası", "de": "Aktionsort"},
    "lg_rings": {
        "en": "Dashed rings: 5, 10, 20 units around the event player",
        "tr": "Kesikli halkalar: aksiyon oyuncusunun çevresinde 5, 10, 20 birim",
        "de": "Gestrichelte Ringe: 5, 10, 20 Einheiten um den ausführenden Spieler",
    },
    "lg_area": {
        "en": "Light area: camera view",
        "tr": "Açık renkli alan: kamera görüntüsü",
        "de": "Helle Fläche: Kamerabild",
    },
    "lg_direction": {
        "en": "{team} attack from left to right",
        "tr": "{team} soldan sağa hücum ediyor",
        "de": "{team} greift von links nach rechts an",
    },
    "pitch_hint": {
        "en": "Point at a player for details; scroll to zoom.",
        "tr": "Ayrıntı için oyuncunun üzerine gelin; yakınlaştırmak için kaydırın.",
        "de": "Für Details auf einen Spieler zeigen; Scrollen zoomt.",
    },
    "pitch_alt": {
        "en": "Pitch with the players visible at {player}'s action",
        "tr": "{player} aksiyonu anında görünen oyuncularla saha",
        "de": "Spielfeld mit den sichtbaren Spielern bei der Aktion von {player}",
    },
    "tt_who": {"en": "Player", "tr": "Oyuncu", "de": "Spieler"},
    "tt_teammate": {"en": "{team} · teammate", "tr": "{team} · takım arkadaşı", "de": "{team} · Mitspieler"},
    "tt_opponent": {"en": "{team} · opponent", "tr": "{team} · rakip", "de": "{team} · Gegenspieler"},
    "tt_keeper": {"en": "goalkeeper", "tr": "kaleci", "de": "Torwart"},
    "tt_distance": {
        "en": "Distance to {player}", "tr": "{player} ile mesafe", "de": "Abstand zu {player}",
    },
    "tt_position": {"en": "Position (x, y)", "tr": "Konum (x, y)", "de": "Position (x, y)"},
    "event": {"en": "Action", "tr": "Aksiyon", "de": "Aktion"},
    "kv_type": {"en": "Action type", "tr": "Aksiyon türü", "de": "Aktionstyp"},
    "kv_team": {"en": "Team", "tr": "Takım", "de": "Team"},
    "kv_player": {"en": "Player", "tr": "Oyuncu", "de": "Spieler"},
    "kv_time": {"en": "Time", "tr": "Dakika", "de": "Spielzeit"},
    "kv_frame": {"en": "360° snapshot", "tr": "360° görüntü", "de": "360°-Aufnahme"},
    "frame_yes": {"en": "available", "tr": "var", "de": "vorhanden"},
    "frame_no": {"en": "not available", "tr": "yok", "de": "nicht vorhanden"},
    "context": {
        "en": "Situation at this moment", "tr": "Bu andaki durum", "de": "Situation in diesem Moment",
    },
    "kv_status": {"en": "Calculation", "tr": "Hesaplama", "de": "Berechnung"},
    "kv_teammates": {
        "en": "Teammates in the picture", "tr": "Görüntüdeki takım arkadaşları", "de": "Mitspieler im Bild",
    },
    "kv_opponents": {
        "en": "Opponents in the picture", "tr": "Görüntüdeki rakipler", "de": "Gegenspieler im Bild",
    },
    "kv_nearest": {
        "en": "Nearest opponent in the picture", "tr": "Görüntüdeki en yakın rakip",
        "de": "Nächster Gegenspieler im Bild",
    },
    "kv_within": {
        "en": "Within {radius} units · teammates / opponents",
        "tr": "{radius} birim içinde · arkadaş / rakip",
        "de": "Im Umkreis von {radius} Einheiten · Mit- / Gegenspieler",
    },
    "radius_title": {
        "en": "Players in the picture within each ring",
        "tr": "Her halkanın içinde görüntüdeki oyuncular",
        "de": "Spieler im Bild innerhalb jedes Rings",
    },
    "col_radius": {"en": "Ring", "tr": "Halka", "de": "Ring"},
    "col_teammates": {"en": "Teammates", "tr": "Takım arkadaşı", "de": "Mitspieler"},
    "col_opponents": {"en": "Opponents", "tr": "Rakip", "de": "Gegenspieler"},
    "tile_teammates": {"en": "Teammates in the picture", "tr": "Görüntüdeki takım arkadaşı", "de": "Mitspieler im Bild"},
    "tile_opponents": {"en": "Opponents in the picture", "tr": "Görüntüdeki rakip", "de": "Gegenspieler im Bild"},
    "tile_nearest": {"en": "Nearest opponent", "tr": "En yakın rakip", "de": "Nächster Gegenspieler"},
    "kv_actor_event": {
        "en": "Player ↔ recorded action spot", "tr": "Oyuncu ↔ aksiyon noktası",
        "de": "Spieler ↔ erfasster Aktionsort",
    },
    "units": {"en": "units", "tr": "birim", "de": "Einheiten"},
    "diagnostics": {
        "en": "Technical details: all fields", "tr": "Teknik ayrıntılar: tüm alanlar",
        "de": "Technische Details: alle Felder",
    },
    "field": {"en": "field", "tr": "alan", "de": "Feld"},
    "value": {"en": "value", "tr": "değer", "de": "Wert"},
    "saved_csv": {
        "en": "Saved spatial_context.csv: {status}{detail}. The values shown are always recomputed from "
              "verified inputs.",
        "tr": "Kayıtlı spatial_context.csv: {status}{detail}. Gösterilen değerler her zaman doğrulanmış "
              "girdilerden yeniden hesaplanır.",
        "de": "Gespeicherte spatial_context.csv: {status}{detail}. Die angezeigten Werte werden immer aus "
              "geprüften Eingaben neu berechnet.",
    },
    "rounding_note": {
        "en": "Values are rounded for display only (coordinates and distances to three decimals; '<0.001' marks a "
              "distance above 0 but below 0.001). Calculations and saved files keep full precision.",
        "tr": "Değerler yalnızca gösterim için yuvarlanır (koordinatlar ve mesafeler üç ondalık; '<0.001', 0'dan "
              "büyük ama 0.001'den küçük bir mesafedir). Hesaplamalar ve kayıtlı dosyalar tam hassasiyeti korur.",
        "de": "Werte werden nur für die Anzeige gerundet (Koordinaten und Abstände auf drei Dezimalstellen; "
              "'<0.001' steht für einen Abstand über 0, aber unter 0.001). Berechnungen und gespeicherte Dateien "
              "behalten die volle Genauigkeit.",
    },
    "explorer_scope": {
        "en": "Snapshots at action moments: not tracking data, and not a measure of player quality.",
        "tr": "Aksiyon anlarındaki görüntülerdir: takip (tracking) verisi değildir ve oyuncu kalitesini ölçmez.",
        "de": "Momentaufnahmen zu Aktionszeitpunkten: keine Trackingdaten und kein Maß für Spielerqualität.",
    },
    # --- values ---
    "null": {"en": "not computed", "tr": "hesaplanmadı", "de": "nicht berechnet"},
    "true": {"en": "yes", "tr": "evet", "de": "ja"},
    "false": {"en": "no", "tr": "hayır", "de": "nein"},
    "status_computed": {"en": "computed", "tr": "hesaplandı", "de": "berechnet"},
    "status_no_frame": {"en": "no 360° snapshot", "tr": "360° görüntü yok", "de": "keine 360°-Aufnahme"},
    "status_duplicate_frames": {
        "en": "several snapshots", "tr": "birden fazla görüntü", "de": "mehrere Aufnahmen",
    },
    "status_freeze_frame_malformed": {
        "en": "snapshot unreadable", "tr": "görüntü okunamadı", "de": "Aufnahme fehlerhaft",
    },
    "status_actor_selection_ambiguous": {
        "en": "event player unclear", "tr": "aksiyon oyuncusu belirsiz", "de": "ausführender Spieler unklar",
    },
    "status_no_actor": {
        "en": "event player not marked", "tr": "aksiyon oyuncusu işaretli değil",
        "de": "ausführender Spieler nicht markiert",
    },
    "status_multiple_actors": {
        "en": "several players marked", "tr": "birden fazla oyuncu işaretli", "de": "mehrere Spieler markiert",
    },
    "status_actor_location_invalid": {
        "en": "player position invalid", "tr": "oyuncu konumu geçersiz", "de": "Spielerposition ungültig",
    },
    "cmp_matches saved CSV": {"en": "matches", "tr": "eşleşiyor", "de": "stimmt überein"},
    "cmp_differs from saved CSV": {"en": "differs", "tr": "farklı", "de": "weicht ab"},
    "cmp_absent": {"en": "not found", "tr": "bulunamadı", "de": "nicht gefunden"},
    "cmp_unreadable": {"en": "unreadable", "tr": "okunamıyor", "de": "nicht lesbar"},
    "cmp_duplicate rows in saved CSV": {
        "en": "duplicate rows", "tr": "yinelenen satırlar", "de": "doppelte Zeilen",
    },
    "cmp_event missing from saved CSV": {
        "en": "action missing", "tr": "aksiyon eksik", "de": "Aktion fehlt",
    },
    # --- notices ---
    "notice_no_frame": {
        "en": "There is no 360° snapshot for this action, so the situation values are not computed. "
              "'Not computed' is not the same as 0.",
        "tr": "Bu aksiyon için 360° anlık görüntü yok; bu yüzden durum değerleri hesaplanmadı. "
              "'Hesaplanmadı' ile 0 aynı şey değildir.",
        "de": "Für diese Aktion gibt es keine 360°-Momentaufnahme, daher sind die Werte nicht berechnet. "
              "„Nicht berechnet“ ist nicht dasselbe wie 0.",
    },
    "notice_not_computed": {
        "en": "The situation values were not computed: {status}. 'Not computed' is not the same as 0.",
        "tr": "Durum değerleri hesaplanmadı: {status}. 'Hesaplanmadı' ile 0 aynı şey değildir.",
        "de": "Die Werte wurden nicht berechnet: {status}. „Nicht berechnet“ ist nicht dasselbe wie 0.",
    },
    "notice_excluded": {
        "en": "{count} entries in the snapshot were left out because their position or team marker is invalid; "
              "the counts cover the remaining players.",
        "tr": "Anlık görüntüdeki {count} kayıt, konumu veya takım işareti geçersiz olduğu için dışarıda bırakıldı; "
              "sayılar kalan oyuncuları kapsar.",
        "de": "{count} Einträge der Momentaufnahme wurden ausgelassen, weil Position oder Teamkennzeichen ungültig "
              "sind; die Zählungen beziehen sich auf die übrigen Spieler.",
    },
    "notice_outside": {
        "en": "{count} position(s) lie outside the 120 × 80 pitch grid. They are drawn where recorded, not moved "
              "onto the pitch.",
        "tr": "{count} konum 120 × 80 saha ızgarasının dışında. Kaydedildikleri yerde çizilir, sahaya taşınmaz.",
        "de": "{count} Position(en) liegen außerhalb des 120 × 80-Rasters. Sie werden wie erfasst gezeichnet und "
              "nicht aufs Feld verschoben.",
    },
    "notice_distance": {
        "en": "The player's position in the snapshot is {distance} units from the recorded action spot. Both are "
              "shown; no limit is applied.",
        "tr": "Oyuncunun görüntüdeki konumu, aksiyonun kaydedildiği noktadan {distance} birim uzakta. İkisi de "
              "gösterilir; bir sınır uygulanmaz.",
        "de": "Die Position des Spielers in der Aufnahme liegt {distance} Einheiten vom erfassten Aktionsort "
              "entfernt. Beide werden gezeigt; es gilt kein Grenzwert.",
    },
    "notice_duplicates": {
        "en": "{count} snapshots are linked to this action; none is drawn because it is unclear which one applies.",
        "tr": "Bu aksiyona {count} anlık görüntü bağlı; hangisinin geçerli olduğu belirsiz olduğundan hiçbiri "
              "çizilmez.",
        "de": "Mit dieser Aktion sind {count} Aufnahmen verknüpft; keine wird gezeichnet, da unklar ist, welche "
              "gilt.",
    },
    # --- plot ---
    "plot_pitch": {"en": "pitch (120 × 80 grid)", "tr": "saha (120 × 80 ızgara)", "de": "Spielfeld (120 × 80-Raster)"},
    "plot_event_location": {
        "en": "recorded action spot", "tr": "aksiyon noktası", "de": "erfasster Aktionsort",
    },
    "plot_teammate": {"en": "teammate", "tr": "takım arkadaşı", "de": "Mitspieler"},
    "plot_opponent": {"en": "opponent", "tr": "rakip", "de": "Gegenspieler"},
    "plot_unknown": {"en": "team marker missing", "tr": "takım işareti eksik", "de": "Teamkennzeichen fehlt"},
    "plot_keeper": {"en": "goalkeeper", "tr": "kaleci", "de": "Torwart"},
    "plot_actor": {"en": "event player", "tr": "aksiyon oyuncusu", "de": "ausführender Spieler"},
    "plot_radii": {
        "en": "distance rings: {radii} units", "tr": "mesafe halkaları: {radii} birim",
        "de": "Abstandsringe: {radii} Einheiten",
    },
    "plot_area": {"en": "camera view (as recorded)", "tr": "kamera görüntüsü (kayıtlı)", "de": "Kamerabild (erfasst)"},
    "plot_no_frame": {
        "en": "No 360° snapshot for this action",
        "tr": "Bu aksiyon için 360° görüntü yok",
        "de": "Keine 360°-Aufnahme für diese Aktion",
    },
    "plot_duplicates": {
        "en": "{count} snapshots linked to this action; none is drawn",
        "tr": "Bu aksiyona {count} görüntü bağlı; hiçbiri çizilmez",
        "de": "{count} Aufnahmen mit dieser Aktion verknüpft; keine wird gezeichnet",
    },
    "plot_attacking": {"en": "attacking direction", "tr": "hücum yönü", "de": "Angriffsrichtung"},
    # --- guide ---
    "guide_use": {
        "en": """**Match overview**

1. Choose a match with the menu in the header. The header shows the competition, round, date, and the score as recorded in the source.
2. *Team comparison* puts both teams' counts side by side (home blue, away orange). Each bar is the team's share of the two teams' total in that row.
3. *Players in this match* has one table per team with every player's counts. Point at a column header for its full definition. The order (team, then player ID) is not a ranking.

**360° moments** (the final)

1. Narrow the actions by action type, team, and player. The player list follows the chosen team, runs from goalkeeper to attack, and shows when a player came on or went off.
2. Pick an action, or step through the list with ‹ and ›. Above the pitch: the player, team, action, and match time. The pitch shows the 360° snapshot of that moment; *Reading the pitch* explains each symbol.
3. *Situation at this moment* (beside the pitch, or below it on narrow screens) shows whether a snapshot exists, how many teammates and opponents were in the picture, the nearest opponent, and the players inside each ring.
4. *Technical details* at the bottom lists every calculated field, including the distance between the player in the snapshot and the recorded action spot.

**Top bar**

- ⟳ reloads the data on disk and checks it again. Data is checked once per session; later changes on disk appear only after this.
- The language menu changes the interface language. Team and player names stay as recorded.

Nothing is downloaded or changed: the app only reads files prepared earlier on this computer.""",
        "tr": """**Maç özeti**

1. Başlıktaki menüden bir maç seçin. Başlıkta turnuva, tur, tarih ve kaynakta kayıtlı skor görünür.
2. *Takım karşılaştırması* iki takımın sayılarını yan yana gösterir (ev sahibi mavi, deplasman turuncu). Her çubuk, o satırdaki iki takım toplamı içinde takımın payıdır.
3. *Bu maçtaki oyuncular* her takım için ayrı bir tabloda oyuncuların sayılarını gösterir. Tam tanım için imleci sütun başlığının üzerine getirin. Sıra (takım, ardından oyuncu ID'si) bir başarı sıralaması değildir.

**360° anlar** (final maçı)

1. Aksiyonları aksiyon türü, takım ve oyuncuya göre daraltın. Oyuncu listesi seçilen takıma göre değişir, kaleciden hücuma doğru sıralanır ve oyuncunun oyuna ne zaman girip çıktığını gösterir.
2. Bir aksiyon seçin ya da listede ‹ ve › ile ilerleyin. Sahanın üstünde: oyuncu, takım, aksiyon ve maç dakikası. Saha, o anın 360° anlık görüntüsünü gösterir; her işaretin anlamı *Saha nasıl okunur* sekmesindedir.
3. *Bu andaki durum* (sahanın yanında, dar ekranlarda altında) anlık görüntünün olup olmadığını, görüntüde kaç takım arkadaşı ve rakip olduğunu, en yakın rakibi ve her halkanın içindeki oyuncuları gösterir.
4. En alttaki *Teknik ayrıntılar* hesaplanan tüm alanları listeler; görüntüdeki oyuncu ile aksiyonun kaydedildiği nokta arasındaki mesafe de buradadır.

**Üst çubuk**

- ⟳ diskteki veriyi yeniden yükler ve tekrar doğrular. Veri her oturumda bir kez doğrulanır; diskteki sonraki değişiklikler ancak bundan sonra görünür.
- Dil menüsü arayüz dilini değiştirir. Takım ve oyuncu adları kaynaktaki gibi kalır.

Hiçbir şey indirilmez veya değiştirilmez: uygulama yalnızca bu bilgisayarda önceden hazırlanmış dosyaları okur.""",
        "de": """**Spielübersicht**

1. Wählen Sie im Menü im Kopfbereich ein Spiel. Der Kopfbereich zeigt Wettbewerb, Runde, Datum und das in der Quelle erfasste Ergebnis.
2. *Teamvergleich* stellt die Werte beider Teams nebeneinander (Heim blau, Gast orange). Jeder Balken ist der Anteil des Teams an der Summe beider Teams in dieser Zeile.
3. *Spieler in diesem Spiel* zeigt je Team eine Tabelle mit den Werten jedes Spielers. Für die vollständige Definition mit der Maus auf eine Spaltenüberschrift zeigen. Die Reihenfolge (Team, dann Spieler-ID) ist keine Rangliste.

**360°-Momente** (das Finale)

1. Grenzen Sie die Aktionen nach Aktionstyp, Team und Spieler ein. Die Spielerliste folgt dem gewählten Team, ist vom Torwart bis zum Angriff geordnet und zeigt Ein- und Auswechslungen.
2. Wählen Sie eine Aktion oder blättern Sie mit ‹ und › durch die Liste. Über dem Spielfeld: Spieler, Team, Aktion und Spielzeit. Das Spielfeld zeigt die 360°-Momentaufnahme dieses Augenblicks; *Das Spielfeld lesen* erklärt jedes Symbol.
3. *Situation in diesem Moment* (neben dem Spielfeld, auf schmalen Bildschirmen darunter) zeigt, ob eine Aufnahme existiert, wie viele Mit- und Gegenspieler im Bild waren, den nächsten Gegenspieler und die Spieler in jedem Ring.
4. *Technische Details* ganz unten listet alle berechneten Felder, darunter den Abstand zwischen dem Spieler in der Aufnahme und dem erfassten Aktionsort.

**Obere Leiste**

- ⟳ lädt die Daten von der Festplatte neu und prüft sie erneut. Die Daten werden einmal pro Sitzung geprüft; spätere Änderungen erscheinen erst danach.
- Das Sprachmenü ändert die Sprache der Oberfläche. Team- und Spielernamen bleiben wie erfasst.

Es wird nichts heruntergeladen oder verändert: Die App liest nur Dateien, die auf diesem Rechner vorbereitet wurden.""",
    },
    "guide_pitch": {
        "en": """A 360° snapshot is a picture of a single moment: where the players visible in the broadcast footage stood when the action happened. It is not a video and not tracking data — nothing between two actions is recorded.

- **★ Gold star** — the player who performed the action. This is the only player the data names.
- **● Coloured dots** — the other players in the picture, in their team's colour. The data does not name them.
- **◯ White ring** — a player marked as a goalkeeper.
- **◇ Diamond** — where the action itself was recorded. It is usually on or very near the star.
- **Dashed rings** (switch *Distance rings*) — 5, 10, and 20 units around the star. *Situation at this moment* counts the players inside each ring.
- **Light area** (switch *Camera view*) — the part of the pitch the camera showed, as recorded by the provider and not checked here. Players outside it were mostly not visible; the provider notes that some may have been placed by hand.
- **➜ Arrow** — attacking direction of the team that performed the action. In 360° data that team always attacks from left (0) to right (120).

Point at a player for their team, the distance to the star, and the position. Scroll to zoom, drag to move, double-click to reset.

Players who are not drawn were simply not in the picture; that does not mean they were absent. Only the event player is named. Units come from the provider's 120 × 80 pitch grid and are not metres.""",
        "tr": """360° anlık görüntü tek bir anın resmidir: aksiyon olduğu anda yayın görüntüsünde görünen oyuncuların nerede durduğu. Video veya takip (tracking) verisi değildir — iki aksiyon arasında olanlar kaydedilmez.

- **★ Altın yıldız** — aksiyonu yapan oyuncu. Verinin adını verdiği tek oyuncudur.
- **● Renkli noktalar** — görüntüdeki diğer oyuncular, takımlarının renginde. Veri bu oyuncuların adını vermez.
- **◯ Beyaz halka** — kaleci olarak işaretlenen oyuncu.
- **◇ Elmas** — aksiyonun kaydedildiği nokta. Genellikle yıldızın üstünde ya da çok yakınındadır.
- **Kesikli halkalar** (*Mesafe halkaları* anahtarı) — yıldızın çevresinde 5, 10 ve 20 birim. *Bu andaki durum* her halkanın içindeki oyuncuları sayar.
- **Açık renkli alan** (*Kamera görüntüsü* anahtarı) — kameranın gösterdiği saha bölümü; sağlayıcının kaydettiği gibidir, burada doğrulanmamıştır. Dışındaki oyuncular çoğunlukla görünmüyordu; sağlayıcıya göre bazıları elle yerleştirilmiş olabilir.
- **➜ Ok** — aksiyonu yapan takımın hücum yönü. 360° verisinde bu takım her zaman soldan (0) sağa (120) hücum eder.

Takımını, yıldıza mesafesini ve konumunu görmek için imleci bir oyuncunun üzerine getirin. Yakınlaştırmak için kaydırın, taşımak için sürükleyin, sıfırlamak için çift tıklayın.

Çizilmeyen oyuncular yalnızca görüntüde değildi; bu, sahada olmadıkları anlamına gelmez. Yalnızca aksiyonu yapan oyuncunun adı bilinir. Birimler sağlayıcının 120 × 80 saha ızgarasındandır, metre değildir.""",
        "de": """Eine 360°-Momentaufnahme ist das Bild eines einzigen Augenblicks: wo die im TV-Bild sichtbaren Spieler standen, als die Aktion stattfand. Sie ist kein Video und keine Trackingdaten – zwischen zwei Aktionen wird nichts erfasst.

- **★ Goldener Stern** – der Spieler, der die Aktion ausführt. Nur ihn nennen die Daten namentlich.
- **● Farbige Punkte** – die übrigen Spieler im Bild, in der Farbe ihres Teams. Die Daten nennen sie nicht.
- **◯ Weißer Ring** – ein als Torwart markierter Spieler.
- **◇ Raute** – der erfasste Ort der Aktion. Meist direkt am Stern oder sehr nah daran.
- **Gestrichelte Ringe** (Schalter *Abstandsringe*) – 5, 10 und 20 Einheiten um den Stern. *Situation in diesem Moment* zählt, wie viele Spieler in jedem Ring stehen.
- **Helle Fläche** (Schalter *Kamerabild*) – der Teil des Spielfelds, den die Kamera zeigte, wie vom Anbieter erfasst und hier nicht geprüft. Spieler außerhalb waren meist nicht sichtbar; laut Anbieter können einige manuell platziert sein.
- **➜ Pfeil** – Angriffsrichtung des Teams, das die Aktion ausführt. In 360°-Daten greift dieses Team immer von links (0) nach rechts (120) an.

Mit der Maus auf einen Spieler zeigen, um Team, Abstand zum Stern und Position zu sehen. Scrollen zum Zoomen, Ziehen zum Verschieben, Doppelklick zum Zurücksetzen.

Nicht gezeichnete Spieler waren nur nicht im Bild – das heißt nicht, dass sie fehlten. Nur der ausführende Spieler ist namentlich bekannt. Die Einheiten stammen aus dem 120 × 80-Raster des Anbieters und sind keine Meter.""",
    },
    "guide_terms": {
        "en": """- **Pressure** — a player closes down an opponent who is receiving, carrying, or releasing the ball (the provider's definition).
- **Counter-press** — the provider's marker for pressing actions within 5 seconds of an open-play turnover.
- **Counterpress-flagged events — supported types** — actions of the seven types that can carry this marker.
- **Event player** — the player who performed the selected action; called the *actor* in 360° data.
- **360° snapshot** — the positions of the visible players at the moment of an action.
- **In the picture** — visible in the snapshot. Players outside the picture are not counted.
- **Not computed** — the value could not be calculated, for example because there is no snapshot. It is not the same as 0: 0 means it was calculated and no player qualified.
- **Units** — the provider's 120 × 80 pitch grid. The documentation does not name the unit (pass lengths are given in yards); they are not metres.
- **Raw counts** — totals are plain counts: not normalized for playing time, number of matches, or opportunities, and not ratings.

Data: StatsBomb Open Data. Analysis shown here must credit StatsBomb.""",
        "tr": """- **Pres** — bir oyuncunun topu alan, süren veya oynayan rakibin üzerine gitmesi (sağlayıcının tanımı).
- **Karşı pres (gegenpress)** — açık oyunda topun el değiştirmesinden sonraki 5 saniye içindeki pres aksiyonları için sağlayıcının koyduğu işaret.
- **Karşı pres işaretli aksiyonlar — desteklenen türler** — bu işareti taşıyabilen yedi aksiyon türündeki aksiyonlar.
- **Aksiyon oyuncusu** — seçilen aksiyonu yapan oyuncu; 360° verisinde *actor* olarak geçer.
- **360° anlık görüntü** — aksiyon anında görünen oyuncuların konumları.
- **Görüntüde** — anlık görüntüde görünür. Görüntü dışındaki oyuncular sayılmaz.
- **Hesaplanmadı** — değer hesaplanamadı, örneğin anlık görüntü olmadığı için. 0 ile aynı değildir: 0, hesaplandığı ve koşulu sağlayan oyuncu olmadığı anlamına gelir.
- **Birim** — sağlayıcının 120 × 80 saha ızgarası. Belgeler birimi belirtmez (pas uzunlukları yarda cinsindendir); metre değildir.
- **Ham sayılar** — toplamlar basit sayımlardır: oynanan süreye, maç sayısına veya fırsatlara göre normalize edilmemiştir ve performans puanı değildir.

Veri: StatsBomb Open Data. Burada gösterilen analizlerde StatsBomb kaynak olarak belirtilmelidir.""",
        "de": """- **Pressing** – ein Spieler läuft einen Gegner an, der den Ball annimmt, führt oder abspielt (Definition des Anbieters).
- **Gegenpressing** – Markierung des Anbieters für Pressingaktionen innerhalb von 5 Sekunden nach einem Ballbesitzwechsel aus dem laufenden Spiel.
- **Aktionen mit Gegenpressing-Markierung — unterstützte Typen** – Aktionen der sieben Typen, die diese Markierung tragen können.
- **Ausführender Spieler** – der Spieler, der die gewählte Aktion ausführt; in 360°-Daten *actor* genannt.
- **360°-Momentaufnahme** – die Positionen der sichtbaren Spieler im Moment einer Aktion.
- **Im Bild** – in der Aufnahme sichtbar. Spieler außerhalb des Bildes werden nicht gezählt.
- **Nicht berechnet** – der Wert konnte nicht berechnet werden, etwa weil keine Aufnahme existiert. Das ist nicht dasselbe wie 0: 0 heißt, er wurde berechnet und kein Spieler erfüllte die Bedingung.
- **Einheiten** – das 120 × 80-Raster des Anbieters. Die Dokumentation nennt keine Einheit (Passlängen sind in Yards angegeben); es sind keine Meter.
- **Rohwerte** – Summen sind einfache Zählungen: nicht nach Spielzeit, Spielanzahl oder Gelegenheiten normiert und keine Bewertung.

Daten: StatsBomb Open Data. Hier gezeigte Analysen müssen StatsBomb als Quelle nennen.""",
    },
}

# Event-type names as the source records them, with common football
# terms in Turkish and German. English shows the source name.
EVENT_TYPES = {
    "Pass": {"tr": "Pas", "de": "Pass"},
    "Ball Receipt*": {"tr": "Top alma", "de": "Ballannahme"},
    "Carry": {"tr": "Top sürme", "de": "Ballführung"},
    "Pressure": {"tr": "Pres", "de": "Pressing"},
    "Ball Recovery": {"tr": "Top kazanma", "de": "Ballgewinn"},
    "Duel": {"tr": "İkili mücadele", "de": "Zweikampf"},
    "Clearance": {"tr": "Uzaklaştırma", "de": "Klärung"},
    "Block": {"tr": "Blok", "de": "Block"},
    "Goal Keeper": {"tr": "Kaleci aksiyonu", "de": "Torwartaktion"},
    "Dribble": {"tr": "Çalım", "de": "Dribbling"},
    "Shot": {"tr": "Şut", "de": "Schuss"},
    "Dispossessed": {"tr": "Top kaptırma", "de": "Ballverlust"},
    "Foul Committed": {"tr": "Yapılan faul", "de": "Begangenes Foul"},
    "Foul Won": {"tr": "Kazanılan faul", "de": "Erlittenes Foul"},
    "Miscontrol": {"tr": "Hatalı top kontrolü", "de": "Verunglückte Ballkontrolle"},
    "Dribbled Past": {"tr": "Çalımlanma", "de": "Ausgedribbelt"},
    "50/50": {"tr": "Ortada kalan top (50/50)", "de": "50:50-Ball"},
    "Substitution": {"tr": "Oyuncu değişikliği", "de": "Auswechslung"},
    "Injury Stoppage": {"tr": "Sakatlık arası", "de": "Verletzungsunterbrechung"},
    "Interception": {"tr": "Top kesme", "de": "Abgefangener Ball"},
    "Half Start": {"tr": "Devre başlangıcı", "de": "Halbzeitbeginn"},
    "Half End": {"tr": "Devre sonu", "de": "Halbzeitende"},
    "Tactical Shift": {"tr": "Taktik değişiklik", "de": "Taktische Umstellung"},
    "Starting XI": {"tr": "İlk 11", "de": "Startelf"},
    "Referee Ball-Drop": {"tr": "Hakem atışı", "de": "Schiedsrichterball"},
    "Shield": {"tr": "Topu koruma", "de": "Ball abschirmen"},
    "Error": {"tr": "Hata", "de": "Fehler"},
    "Offside": {"tr": "Ofsayt", "de": "Abseits"},
    "Own Goal Against": {"tr": "Kendi kalesine gol", "de": "Eigentor"},
    "Own Goal For": {"tr": "Rakibin kendi kalesine golü", "de": "Eigentor des Gegners"},
    "Player Off": {"tr": "Oyuncu sahadan çıktı", "de": "Spieler verlässt das Feld"},
    "Player On": {"tr": "Oyuncu sahaya döndü", "de": "Spieler zurück auf dem Feld"},
    "Bad Behaviour": {"tr": "Sportmenliğe aykırı hareket", "de": "Unsportliches Verhalten"},
}

# Position names as the source records them in `tactics.lineup`.
POSITIONS = {
    "Goalkeeper": {"tr": "Kaleci", "de": "Torwart"},
    "Right Back": {"tr": "Sağ bek", "de": "Rechtsverteidiger"},
    "Right Center Back": {"tr": "Sağ stoper", "de": "Rechter Innenverteidiger"},
    "Center Back": {"tr": "Stoper", "de": "Innenverteidiger"},
    "Left Center Back": {"tr": "Sol stoper", "de": "Linker Innenverteidiger"},
    "Left Back": {"tr": "Sol bek", "de": "Linksverteidiger"},
    "Right Wing Back": {"tr": "Sağ kanat bek", "de": "Rechter Schienenspieler"},
    "Left Wing Back": {"tr": "Sol kanat bek", "de": "Linker Schienenspieler"},
    "Right Defensive Midfield": {"tr": "Sağ ön libero", "de": "Rechter defensiver Mittelfeldspieler"},
    "Center Defensive Midfield": {"tr": "Ön libero", "de": "Defensiver Mittelfeldspieler"},
    "Left Defensive Midfield": {"tr": "Sol ön libero", "de": "Linker defensiver Mittelfeldspieler"},
    "Right Midfield": {"tr": "Sağ orta saha", "de": "Rechtes Mittelfeld"},
    "Right Center Midfield": {"tr": "Sağ merkez orta saha", "de": "Rechter zentraler Mittelfeldspieler"},
    "Center Midfield": {"tr": "Merkez orta saha", "de": "Zentraler Mittelfeldspieler"},
    "Left Center Midfield": {"tr": "Sol merkez orta saha", "de": "Linker zentraler Mittelfeldspieler"},
    "Left Midfield": {"tr": "Sol orta saha", "de": "Linkes Mittelfeld"},
    "Right Attacking Midfield": {"tr": "Sağ ofansif orta saha", "de": "Rechter offensiver Mittelfeldspieler"},
    "Center Attacking Midfield": {"tr": "Ofansif orta saha", "de": "Offensiver Mittelfeldspieler"},
    "Left Attacking Midfield": {"tr": "Sol ofansif orta saha", "de": "Linker offensiver Mittelfeldspieler"},
    "Right Wing": {"tr": "Sağ kanat", "de": "Rechtsaußen"},
    "Left Wing": {"tr": "Sol kanat", "de": "Linksaußen"},
    "Right Center Forward": {"tr": "Sağ forvet", "de": "Rechter Stürmer"},
    "Center Forward": {"tr": "Santrfor", "de": "Mittelstürmer"},
    "Striker": {"tr": "Santrfor", "de": "Mittelstürmer"},
    "Left Center Forward": {"tr": "Sol forvet", "de": "Linker Stürmer"},
    "Secondary Striker": {"tr": "İkinci forvet", "de": "Hängende Spitze"},
}


def t(key, language=DEFAULT_LANGUAGE, **values):
    """The text for `key` in `language`, with placeholders filled in."""
    entry = TEXT[key]
    return entry.get(language, entry[DEFAULT_LANGUAGE]).format(**values)


def source_name(table, name, language=DEFAULT_LANGUAGE):
    """A source name (event type or position) in `language`; unknown names are shown as recorded."""
    if language == DEFAULT_LANGUAGE or name not in table:
        return name
    return table[name].get(language, name)
