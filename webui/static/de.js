/* German for the 𝕭𝖗𝖚𝖘𝖈𝖍𝖔𝖑𝖔𝖌𝖎𝖘𝖈𝖍𝖊𝖗 𝕶𝖔𝖓𝖌𝖗𝖊𝖘𝖘 theme.
 *
 * Every string the interface can show, in one file, so translating is reading
 * a dictionary rather than hunting through markup and JavaScript. webui.js
 * applies it while that theme is on and puts the English back when it goes off.
 *
 *   text     an English string -> its German. The key is the English with its
 *            whitespace collapsed, which is how the page is matched against it,
 *            so a sentence wrapped over four lines in a template is one entry.
 *            Used for text, for title/aria-label/alt/placeholder, and for the
 *            strings webui.js builds itself — those carry {placeholders} that
 *            survive into the German.
 *   html     a data-i18n id -> German markup. For prose that has tags inside
 *            it, where German word order will not line up with the English
 *            fragments between them.
 *   patterns [regexp source, German with $1, $2 …]. For text the server writes
 *            with a detail interpolated into it, which no fixed key can match.
 *
 * The vocabulary is fixed on purpose, so the same thing is called the same
 * thing everywhere: bed → Arbeitsfläche, canvas/image area → Druckbereich,
 * tray/container/cup → Behälter, G-code → Maschinensteuerbefehle, stroke →
 * Strich, travel → Leerfahrt, backlash → Umkehrspiel, woodcut → Holzschnitt,
 * the cut → Druckvorlage.
 */
window.KONGRESS_DE = {

text: {

/* ------------------------------------------------------------------ chrome */
"Brušograf WebUI": "Brušograf Weboberfläche",
"About — Brušograf WebUI": "Wie es funktioniert — Brušograf Weboberfläche",
"Brušograf WebUI — turn pictures into G-code for brush plotters.":
  "Brušograf Weboberfläche — verwandelt Bilder in Maschinensteuerbefehle für Pinselplotter.",
"Machine": "Maschine",
"Choose a machine…": "Maschine wählen …",
"Or use your own": "Oder eigene verwenden",
"Choose file": "Datei auswählen",
"No file selected": "Keine Datei ausgewählt",
"No machines kept yet": "Noch keine Maschinen hinterlegt",
"Upload config to server": "Konfiguration auf den Server laden",
"About keeping a config on the server": "Über das Hinterlegen einer Konfiguration auf dem Server",
"A kept config is added to the machine list above for anyone who opens this page, and stays after the server restarts. Without this, an upload is only yours, and only for as long as your session lasts.":
  "Eine hinterlegte Konfiguration erscheint in der Maschinenliste oben für jeden, der diese Seite öffnet, und bleibt auch nach einem Neustart des Servers erhalten. Ohne dies gehört eine hochgeladene Datei nur Ihnen, und nur so lange, wie Ihre Sitzung währt.",
"Kept on the server, and in the machine list from now on.":
  "Auf dem Server hinterlegt und fortan in der Maschinenliste.",
"Kept on the server as {name}: {original} was already taken by another machine.":
  "Auf dem Server als {name} hinterlegt: {original} war bereits von einer anderen Maschine belegt.",
"Download this config": "Diese Konfiguration herunterladen",
"Choose a machine to begin. Its config sets the trays, the canvas and how the brush behaves.":
  "Wählen Sie zunächst eine Maschine. Ihre Konfiguration bestimmt die Behälter, den Druckbereich und das Verhalten des Pinsels.",
"How this works": "Wie es funktioniert",
"What the machine is doing, and why": "Was die Maschine tut, und warum",
"This turns a picture into the movements a Brushograph makes: where to dip the brush, where to put it down, and the path to drag it along. What comes out is a G-code file you stream to the machine.":
  "Dies verwandelt ein Bild in die Bewegungen, die ein Brušograf ausführt: wo der Pinsel einzutauchen ist, wo er abzusetzen ist und welche Bahn er zu ziehen hat. Heraus kommt eine Datei mit Maschinensteuerbefehlen, die Sie an die Maschine senden.",
"How a run works": "Wie ein Lauf abläuft",
"Notes": "Anmerkungen",
"Themes": "Erscheinungsbilder",
"← Back to the machine": "← Zurück zur Maschine",
"Theme": "Erscheinungsbild",
"Default": "Standard",
"Dark mode": "Dunkelmodus",
"Coconut mode": "Kokosnussmodus",

/* ------------------------------------------------------------ the machine */
"The machine": "Die Maschine",
"Bed, canvas and trays drawn to scale, redrawn as you edit.":
  "Arbeitsfläche, Druckbereich und Behälter maßstabsgerecht, bei jeder Änderung neu gezeichnet.",
"Plan view of the machine bed and its trays": "Aufsicht auf die Arbeitsfläche und ihre Behälter",
"Machine sketch": "Maschinenriss",
"Machine sketch (form has errors)": "Maschinenriss (das Formular enthält Fehler)",
"Machine sketch (could not be drawn)": "Maschinenriss (konnte nicht gezeichnet werden)",
"Machine setup": "Maschineneinrichtung",
"Model, connection, containers, brush heights, speeds, macros — set once per machine":
  "Modell, Verbindung, Behälter, Pinselhöhen, Geschwindigkeiten, Makros — einmalig je Maschine",
"Container positions": "Behälterpositionen",
"Auto-space containers": "Behälter anordnen",
"Set the water cup where the holder actually sits and auto-space the rest based on that. That also sets the lift, dip and swipe for the holder.":
  "Setzen Sie den Wasserbehälter dorthin, wo der Halter tatsächlich sitzt, und ordnen Sie die übrigen von ihm aus an. Dabei werden auch Hub, Eintauchtiefe und Streichzug für den Halter eingestellt.",
"Container setup": "Behältereinrichtung",
"Model": "Modell",
"Back to the {model} settings this config opened with.":
  "Wieder die Einstellungen für den {model}, mit denen diese Konfiguration geöffnet wurde.",
"Set up for the {model}: travel limits, canvas offset, container positions and heights. Check them against the machine.":
  "Für den {model} eingerichtet: Verfahrgrenzen, Versatz des Druckbereichs, Behälterpositionen und -höhen. Prüfen Sie sie an der Maschine.",
"Save these settings": "Einstellungen speichern",
"Download Machine Config": "Maschinenkonfiguration herunterladen",
"Update writes them over the copy kept on this server instead, for everyone who picks it from the machine list.":
  "„Aktualisieren“ schreibt sie stattdessen über die auf diesem Server hinterlegte Fassung, für jeden, der sie aus der Maschinenliste wählt.",
"Updating…": "Wird aktualisiert …",
"Update {name}": "{name} aktualisieren",
"Delete {name}": "{name} löschen",
"Kept as {name} — {requested} on this server is another machine, and it was not written over.":
  "Als {name} hinterlegt — {requested} ist auf diesem Server eine andere Maschine und wurde nicht überschrieben.",
"Update puts them on this server, in the machine list for everyone who opens this page. A name already taken is somebody else's machine and is never written over — this one goes in beside it, and the page says under what name.":
  "„Aktualisieren“ legt sie auf diesem Server ab, in der Maschinenliste für jeden, der diese Seite öffnet. Ein bereits vergebener Name gehört zur Maschine eines anderen und wird niemals überschrieben — diese hier kommt daneben, und die Seite nennt den Namen, den sie bekommen hat.",
"There is no machine config loaded to save.":
  "Es ist keine Maschinenkonfiguration geladen, die hinterlegt werden könnte.",
"Updated {name} on the server.": "{name} auf dem Server aktualisiert.",
"Only a config kept on the server can be updated there.":
  "Nur eine auf dem Server hinterlegte Konfiguration kann dort aktualisiert werden.",
"Macro generator": "Makrogenerator",
"Seven small routines: zeroing the controller through a mostly fixed sequence, parking the brush, replacing paper, washing the brush then parking it, placing a single reference dot on the canvas, painting a tick on the canvas at the X of every container, and drawing the sheet that the play in each axis is measured off — that last one wants a pen fitted where the brush goes and visits no cup, and the container ticks want paint in the black cup, since black is what paints them. Clean follows whichever container shape is set under Containers; calibrate does neither, but it lifts clear like the rest before it crosses — just the dot, and a park over it.":
  "Sieben kleine Abläufe: die Steuerung über eine weitgehend feste Folge auf Null setzen, den Pinsel abstellen, das Papier wechseln, den Pinsel waschen und abstellen, einen einzelnen Bezugspunkt auf den Druckbereich setzen, für jeden Behälter einen Strich bei dessen X auf den Druckbereich malen und das Blatt zeichnen, an dem sich das Spiel beider Achsen messen lässt — für das letzte gehört ein Stift dorthin, wo sonst der Pinsel sitzt, und es fährt keinen Behälter an; für die Behälterstriche gehört Farbe in den schwarzen Behälter, denn Schwarz malt sie. Die Reinigung richtet sich nach der unter „Behälter“ eingestellten Behälterform; die Kalibrierung tut das nicht, hebt aber wie die übrigen ab, ehe sie die Fläche quert — nur der Punkt und eine Ruhestellung darüber.",
"Generate macros": "Steuermakros erzeugen",
"Download macros": "Makros herunterladen",
"Upload to machine": "Auf Maschine übertragen",

/* ---------------------------------------------------------------- artwork */
"Artwork": "Bildvorlage",
"One picture per colour, painted in the order below — or a single colour photograph, split into CMYK and thresholded into those same plates, which puts the four colour cards away. Ink is anything not white.":
  "Ein Bild je Farbe, in der unten angezeigten Reihenfolge gemalt — oder eine einzelne Farbfotografie, in CMYK zerlegt und auf ebendiese Druckplatten geschwellt, was die vier Farbkarten beiseiteräumt. Farbe ist alles, was nicht weiß ist.",
"Colour photograph": "Farbfotografie",
"A colour photograph is converted to CMYK with a paper profile, then each channel is thresholded into a two-tone plate. Those plates are painted exactly as if you had uploaded already-thresholded pictures to Cyan, Magenta, Yellow and Black. Those four cards are put away while a photograph is loaded; remove it to upload plates by hand.":
  "Eine Farbfotografie wird mit einem Papierprofil nach CMYK gewandelt, dann wird jeder Auszug zu einer zweitönigen Druckplatte geschwellt. Diese Platten werden genau so gemalt, als hätten Sie bereits geschwellte Bilder für Cyan, Magenta, Gelb und Schwarz hochgeladen. Jene vier Karten sind beiseitegeräumt, solange eine Fotografie geladen ist; nehmen Sie sie fort, um Platten von Hand hochzuladen.",
"About colour-photograph separation": "Über die Zerlegung der Farbfotografie",
"Picture": "Bild",
"Ink cutoff": "Farbschwelle",
"A tint below the cutoff is left as paper; at or above it becomes that tray's ink. 0 keeps any non-zero tint.":
  "Ein Ton unterhalb der Schwelle bleibt Papier; ab der Schwelle wird er zur Farbe dieses Behälters. 0 behält jeden Ton, der nicht Null ist.",
"Black knocks out the colours": "Schwarz spart die Farben aus",
"Leave cyan, magenta and yellow off wherever black paints. The conversion beds dark tones on all three, the way a press does, and the black pass then covers them: half the painting for no visible change. Untick it to lay that bed anyway, so a black pass slightly out of register shows colour at its edge rather than bare paper.":
  "Cyan, Magenta und Gelb überall dort weglassen, wo Schwarz malt. Die Umwandlung unterlegt dunkle Töne mit allen dreien, wie es eine Druckmaschine tut, und der schwarze Durchgang deckt sie dann zu: die halbe Malarbeit ohne sichtbaren Unterschied. Abwählen, um diese Unterlage dennoch zu malen, damit ein leicht versetzter schwarzer Durchgang an seiner Kante Farbe zeigt statt blankem Papier.",
"Show the plates": "Druckplatten anzeigen",
"CMYK plates from the photograph": "CMYK-Druckplatten der Fotografie",
"What it is": "Bildart",
"Already black and white": "Bereits schwarzweiß",
"A photo — cut it for me": "Ein Foto — bitte umwandeln",
"Turning the photo into a cut": "Das Foto in eine Druckvorlage verwandeln",
"A brush paints or it does not, so a photograph has to become two tones before it can be painted. It becomes strokes: long marks about a brush wide that follow the shapes in the picture, packed tight in the shadows, further apart through the midtones, and gone by the highlights.":
  "Ein Pinsel malt oder er malt nicht, also muss eine Fotografie zweitönig werden, bevor sie gemalt werden kann. Sie wird zu Strichen: langen Marken von etwa einer Pinselbreite, die den Formen im Bild folgen, in den Schatten dicht an dicht, durch die Mitteltöne weiter auseinander und in den Lichtern gar nicht mehr.",
"About the woodcut conversion": "Über die Umwandlung in den Holzschnitt",
"Detail": "Detailgrad",
"Hatching": "Schraffur",
"Darkness": "Schwärzung",
"Edge roughness": "Kantenrauheit",
"Contour lines": "Konturlinien",
"Keep the dark edges in the picture as knife lines.": "Dunkle Bildkanten als Messerlinien beibehalten.",
"Isolate the subject": "Motiv freistellen",
"Insta face filter": "Gesichtsretusche",
"Evens the light on the face and smooths the skin, keeping eyes, brows and lips sharp.":
  "Gleicht das Licht im Gesicht aus und glättet die Haut; Augen, Brauen und Lippen bleiben scharf.",
"Show me the cut": "Druckvorlage anzeigen",
"The photo as it will be painted": "Das Foto, so wie es gemalt wird",
"The picture is scaled to fit this. The height follows the width and the aspect ratio of the first picture you loaded; a portrait colour photograph is turned on its side first.":
  "Das Bild wird auf dieses Maß skaliert. Die Höhe ergibt sich aus der Breite und dem Seitenverhältnis des zuerst geladenen Bildes; eine hochformatige Farbfotografie wird vorher quer gelegt.",
"Picture auto-rotated and scaled as needed to maximize printing area":
  "Bild wird bei Bedarf automatisch gedreht und skaliert, um die Druckfläche auszuschöpfen",

/* -------------------------------------------------------------------- run */
"Run": "Ausführen",
"Check the path, then send it to the machine.":
  "Prüfen Sie die Bahn und senden Sie sie dann an die Maschine.",
"How the brush covers a shape: the gap between strokes, the pattern it lays them in, and how many times it goes round the outline. Zero for the line distance leaves the shapes unfilled.":
  "Wie der Pinsel eine Form deckt: der Abstand zwischen den Strichen, das Muster, in dem er sie legt, und wie oft er die Kontur umrundet. Null als Linienabstand lässt die Formen ungefüllt.",
"Generate G-code": "Maschinensteuerbefehle berechnen",
"▶ Play": "▶ Abspielen",
"❚❚ Pause": "❚❚ Anhalten",
"Send to machine": "An Maschine senden",
"Upload & start": "Übertragen & starten",
"Already have a file?": "Sie haben bereits eine Datei?",
"Open a .gcode": "Eine .gcode öffnen",

/* ------------------------------------------------- sections, groups, trays */
"Trays and Images": "Behälter und Bilder",
"Connection": "Verbindung",
"Brushograph Options": "Brušograf-Einstellungen",
"Fill Options": "Fülleinstellungen",
"Controller Options": "Steuerungseinstellungen",
"Painting dimensions": "Bildmaße und Lage",
"Canvas": "Leinwand",
"Brush control": "Pinselsteuerung",
"Containers": "Behälter",
"Paint management": "Farbverwaltung",
"Backlash": "Umkehrspiel",
"Bed levelling":
  "Nivellierung der Unterlage",
"Z top-left":
  "Z oben links",
"Z top-right":
  "Z oben rechts",
"Z middle":
  "Z Mitte",
"Z bottom-left":
  "Z unten links",
"Z bottom-right":
  "Z unten rechts",
"Write every move made on the paper at the height the paper is at there, from the five readings below. Canvas Height is one figure and a sheet taped to a bed is not one height: a brush set to touch in the middle rides over the paper at one corner and digs in at another, which a watercolour brush shows at a tenth of a millimetre. Off until the five are measured — with all five the same it does nothing anyway.":
  "Schreibt jede Bewegung auf dem Papier in der Höhe, die das Papier dort hat, nach den fünf Messwerten unten. Die Unterlagenhöhe ist eine einzige Zahl, ein aufgeklebtes Blatt aber nicht: ein Pinsel, der in der Mitte aufsetzt, schwebt an der einen Ecke über dem Papier und gräbt sich an der anderen hinein — ein Aquarellpinsel zeigt das schon bei einem Zehntelmillimeter. Aus, bis die fünf gemessen sind; sind alle gleich, bewirkt es ohnehin nichts.",
"How much higher the paper is at the top-left of the canvas than where Canvas Height was set, in millimetres. Take the brush there, lower it until it just touches, and type the difference from Canvas Height. The plan view marks the spot.":
  "Um wie viel höher das Papier oben links auf der Unterlage liegt als dort, wo die Unterlagenhöhe gesetzt wurde (mm). Fahren Sie den Pinsel hin, senken Sie ihn, bis er eben aufsetzt, und tragen Sie die Differenz zur Unterlagenhöhe ein. Die Planansicht zeigt die Stelle.",
"The same reading at the top-right corner of the canvas. The plan view marks the spot.":
  "Derselbe Messwert an der oberen rechten Ecke der Unterlage. Die Planansicht zeigt die Stelle.",
"The same reading at the middle of the canvas. This is the one that catches a twist: three corners fit a plane and can say nothing about a sheet that bellies or a bed that is not flat.":
  "Derselbe Messwert in der Mitte der Unterlage. Dieser fängt die Verwindung ein: drei Ecken legen eine Ebene fest und können nichts über ein durchhängendes Blatt oder ein unebenes Bett sagen.",
"The same reading at the bottom-left corner of the canvas, the corner nearest the containers. The plan view marks the spot.":
  "Derselbe Messwert an der unteren linken Ecke der Unterlage, der Ecke, die den Behältern am nächsten liegt. Die Planansicht zeigt die Stelle.",
"The same reading at the bottom-right corner of the canvas. The plan view marks the spot.":
  "Derselbe Messwert an der unteren rechten Ecke der Unterlage. Die Planansicht zeigt die Stelle.",
"Other settings": "Weitere Einstellungen",
"Moves": "Bewegungen",
"Fast": "Schnell",
"Remove Drops": "Tropfen Abstreifen",
"Water": "Wasser",
"Yellow (Y)": "Gelb (Y)",
"Black (K)": "Schwarz (K)",
/* the tray keys as the G-code and the plan spell them, for the legend */
"Yellow": "Gelb",
"Black": "Schwarz",
"Kroma": "Schwarz",
"Classic": "Klassisch",
"Custom": "Eigene",
/* The fill patterns are named as the slicer names them; the picker reads them
   as words, so the words are translated and the stored value is not. */
"concentric": "konzentrisch",
"archimedeanchords": "archimedische Sehnen",
"alignedrectilinear": "gleichgerichtet geradlinig",
"rectilinear": "geradlinig",
"hilbertcurve": "Hilbertkurve",

/* ----------------------------------------------------------- field labels */
"Width": "Breite",
"Height": "Höhe",
"Offset X": "Versatz X",
"Offset Y": "Versatz Y",
"Max Width": "Größtbreite",
"Max Height": "Größthöhe",
"Canvas Height": "Unterlagenhöhe",
"Canvas Start Y": "Unterlagenbeginn Y",
"Go In Tray Lift": "Hub über dem Behälter",
"Dip Depth": "Tauchtiefe",
"Remove Drops Lift": "Hub beim Abstreifen",
"Move To Other Shape Lift": "Hub zwischen zwei Formen",
"Cup Swipe Exit Z": "Z am Ende des Streichzugs",
"Cup Dip Lanes": "Tauchspuren",
"Paint Per Run Min": "Farbstrecke Mindestens",
"Paint Per Run Max": "Farbstrecke Höchstens",
"Prepare Paint Count": "Anmischgänge",
"Tray Enter Radius": "Eintauchradius",
"Remove Drops Radius": "Abstreifradius",
"Backlash Compensation": "Ausgleich des Umkehrspiels",
"Backlash X": "Umkehrspiel X",
"Backlash X far end": "Umkehrspiel X am fernen Ende",
"Backlash Y": "Umkehrspiel Y",
"Backlash Y far end": "Umkehrspiel Y am fernen Ende",
"Hostname": "Netzwerkname",
"Acc": "Beschleunigung",
"Feedrate 1": "Vorschub 1",
"Feedrate (mm/minute)": "Vorschub (mm/Minute)",
"Feedrate 2": "Vorschub 2",
"Infill Angles": "Füllwinkel",
"Infill Line Distance": "Fülllinienabstand",
"Infill Pattern": "Füllmuster",
"Wall Line Count": "Anzahl Konturlinien",
"Controller Type": "Steuerungstyp",
"Max Width (mm)": "Größte Pinselbreite (mm)",
"Min Path Length (px)": "Kürzeste Bahnlänge (px)",
"Smooth Window Size": "Fensterbreite der Glättung",
"Dip Distance Threshold (mm)": "Strecke bis zum Nachtauchen (mm)",
"Feed Rate": "Vorschub",
"Dip Wipe Radius": "Abstreifradius nach dem Tauchen",
"Z Wipe Travel": "Z beim Abstreifen",
"Dip Entry Radius": "Eintauchradius",
"Remove Drops Enabled": "Tropfen Abstreifen",
"Z Global Offset Val": "Globaler Z-Versatz",
"Z Safe": "Sichere Z-Höhe",
"Z Safe Dip": "Sichere Z-Höhe beim Tauchen",

/* ------------------------------------------------------- the help bubbles */
"Where the machine answers on the network — the name or address of its FluidNC controller, without http://. Used by Send to machine and Upload & start.":
  "Wo die Maschine im Netz antwortet — Name oder Adresse ihrer FluidNC-Steuerung, ohne http://. Wird von „An Maschine senden“ und „Übertragen & starten“ benutzt.",
"Width of a file (mm); you may upload larger files, but they need to be in the same aspect ratio":
  "Breite einer Datei (mm); größere Dateien sind zulässig, müssen aber dasselbe Seitenverhältnis haben",
"Height of a file (mm); you may upload larger files, but they need to be in the same aspect ratio":
  "Höhe einer Datei (mm); größere Dateien sind zulässig, müssen aber dasselbe Seitenverhältnis haben",
"How far right of X0 this painting starts (mm). The picture's own (0,0) corner lands here.":
  "Wie weit rechts von X0 dieses Bild beginnt (mm). Die Ecke (0,0) des Bildes liegt hier.",
"How far past Canvas Start Y this painting starts (mm). 0 puts it at the start of the paintable area, right where the containers end; raise it to paint further up the bed. What the machine is asked for is the two added together.":
  "Wie weit hinter dem Unterlagenbeginn Y dieses Bild anfängt (mm). 0 setzt es an den Anfang der bemalbaren Fläche, genau dort, wo die Behälter enden; erhöhen Sie es, um weiter hinten auf dem Bett zu malen. Die Maschine bekommt die Summe aus beiden.",
"Where the paintable area begins in Y (mm): the far edge of the strip the containers stand in, and a fact about the machine rather than about this painting. Nothing is painted below it, and the painted height is measured from it — with Offset Y at 0 the canvas starts exactly here. Choosing a model sets it: 25 mm on the Mini, 19 on the 𝔐𝔦𝔨𝔯𝔬.":
  "Wo die bemalbare Fläche in Y beginnt (mm): die hintere Kante des Streifens, auf dem die Behälter stehen, und eine Angabe über die Maschine, nicht über dieses Bild. Darunter wird nichts gemalt, und die gemalte Höhe wird von hier aus gemessen — steht der Versatz Y auf 0, beginnt die Unterlage genau hier. Die Wahl des Modells setzt ihn: 25 mm beim Mini, 19 beim 𝔐𝔦𝔨𝔯𝔬.",
"Total width limit of machine (mm), measured from the origin. A painting starts at Offset X, so the widest one is this less that offset.":
  "Größte Breite der Maschine (mm), vom Ursprung aus gemessen. Ein Bild beginnt beim X-Versatz, also ist das breitestmögliche um ebendiesen Versatz geringer.",
"Total height limit of machine (mm), measured from the origin. A painting starts at Canvas Start Y, past the strip the containers stand in, plus whatever Offset Y adds to it, so the tallest one is this less both: 124 mm of Pinkograph's 156.":
  "Größte Höhe der Maschine (mm), vom Ursprung aus gemessen. Ein Bild beginnt beim Unterlagenbeginn Y, hinter dem Streifen, auf dem die Behälter stehen, zuzüglich dessen, was der Versatz Y hinzufügt; das höchstmögliche ist also um beides geringer: 124 mm von Pinkographs 156.",
"Minimum path length (mm) for painting. For plotting set this number really high (e.g. 1000000) to avoid the paint fetching sequence":
  "Kürzeste Bahnlänge (mm) zum Malen. Zum Plotten setzen Sie diese Zahl sehr hoch (z. B. 1000000), damit kein Farbholen stattfindet",
"Maximum path length (mm) for painting. For plotting set this number really high (e.g. 1000000) to avoid the paint fetching sequence":
  "Längste Bahnlänge (mm) zum Malen. Zum Plotten setzen Sie diese Zahl sehr hoch (z. B. 1000000), damit kein Farbholen stattfindet",
"Set canvas height (mm), for thicker surfaces (e.g. ceramic tile)":
  "Höhe der Unterlage (mm), für dickere Untergründe (z. B. eine Keramikfliese)",
"Which openBrushograph this is. Mini is the standard machine; 𝔐𝔦𝔨𝔯𝔬 is the small one, with shorter racks, 12 mm of Z and its own five-crucible CMYK holder. Choosing one sets the travel limits, the canvas offset, the tray lift and the container spacing to suit it.":
  "Welcher openBrushograph dies ist. Der Mini ist die Standardmaschine, der 𝔐𝔦𝔨𝔯𝔬 die kleine, mit kürzeren Zahnstangen, 12 mm Z-Hub und einem eigenen CMYK-Halter mit fünf Näpfen. Die Wahl stellt Verfahrgrenzen, Versatz des Druckbereichs, Hub zum Behälter und Behälterabstände passend ein.",
"Lift on Z-axis when going into a container for color":
  "Hub der Z-Achse beim Anfahren eines Behälters zum Farbholen",
"Classic is the round cup the machine was built around: the brush goes down the middle, sweeps a chord and comes back up. CMYK is the rectangular five-bay holder, whose floor climbs towards the back — there the brush makes one swipe from the deep end to the shallow one, rising as it goes. Custom is rectangular cups swiped the same way, at the sizes and spacing you give below.":
  "„Klassisch“ ist der runde Napf, um den herum die Maschine gebaut wurde: Der Pinsel fährt mittig hinab, streicht eine Sehne und kommt wieder herauf. „CMYK“ ist der rechteckige Halter mit fünf Kammern, dessen Boden nach hinten ansteigt — dort führt der Pinsel einen einzigen Zug vom tiefen zum flachen Ende und steigt dabei an. „Eigene“ sind rechteckige Behälter, die ebenso bestrichen werden, in den Maßen und Abständen, die Sie unten angeben.",
"Custom containers: how wide the water cup is across X, inside (mm). Wider than the colours, so the brush has room to be rinsed.":
  "Eigene Behälter: wie breit der Wasserbehälter in X innen ist (mm). Breiter als die Farben, damit der Pinsel Platz zum Ausspülen hat.",
"Custom containers: how wide each colour cup is across X, inside (mm).":
  "Eigene Behälter: wie breit jeder Farbbehälter in X innen ist (mm).",
"Custom containers: how far the swipe runs along Y, which should stay inside the cup (mm).":
  "Eigene Behälter: wie weit der Zug in Y läuft; er sollte im Behälter bleiben (mm).",
"Custom containers: centre to centre between colour cups along X (mm). The water cup is parted from cyan by the same wall, so Auto-space puts cyan at half of each width plus that wall from the water.":
  "Eigene Behälter: Mittenabstand der Farbbehälter in X (mm). Zwischen Wasser und Cyan liegt dieselbe Wand, also setzt „Behälter anordnen“ Cyan um je die halbe Breite beider plus diese Wand vom Wasser entfernt.",
"Z at the shallow end of the stairs, where the swipe finishes (mm). The swipe starts at Dip Depth, in the paint, and rises to this. Keep it above Canvas Height, or the brush leaves the cup at paper level. Auto-space containers sets it from the holder's design; adjust it on the machine if the brush does not drag up the stairs.":
  "Z am flachen Ende der Stufen, wo der Zug endet (mm). Der Zug beginnt bei der Tauchtiefe, in der Farbe, und steigt bis hierher. Halten Sie ihn über der Unterlagenhöhe, sonst verlässt der Pinsel den Behälter auf Papierhöhe. „Behälter anordnen“ setzt ihn nach dem Entwurf des Halters; passen Sie ihn an der Maschine an, wenn der Pinsel nicht die Stufen hinaufstreicht.",
"Rectangular containers: how many places across the cup the pickups are spread over. The brush goes straight down at one of them, at Dip Depth, and swipes up the stairs from there, and the next pickup uses another — so the paint is mixed by where the brush lands rather than by stirring it. The lanes are evenly spaced over the middle 70% of the cup, 15% off each wall, and are visited out of order so one pickup and the next land at opposite ends of it. 1 puts every pickup down the middle.":
  "Rechteckige Behälter: auf wie viele Stellen quer durch den Behälter die Farbaufnahmen verteilt werden. Der Pinsel fährt an einer davon gerade hinab, auf Tauchtiefe, und streicht von dort die Stufen hinauf; die nächste Aufnahme nimmt eine andere — die Farbe wird also dadurch gemischt, wo der Pinsel aufsetzt, und nicht durch Rühren. Die Spuren liegen gleichmäßig über den mittleren 70% des Behälters, je 15% von jeder Wand entfernt, und werden in versetzter Reihenfolge angefahren, sodass aufeinanderfolgende Aufnahmen an gegenüberliegenden Enden liegen. 1 setzt jede Aufnahme in die Mitte.",
"How far the brush descends into a cup, as a Z coordinate. Negative goes down. Deep enough to reach the paint, no deeper — a shallow petri dish wants far less than a tall pot.":
  "Wie weit der Pinsel in einen Behälter hinabfährt, als Z-Koordinate. Negativ heißt abwärts. Tief genug, um die Farbe zu erreichen, und nicht tiefer — eine flache Petrischale verlangt weit weniger als ein hoher Topf.",
"Lift when exiting the container, so it hits the edge and removes excess color":
  "Hub beim Verlassen des Behälters, damit der Pinsel den Rand streift und überschüssige Farbe abgibt",
"Lift on Z-axis when painting/drawing": "Hub der Z-Achse beim Malen bzw. Zeichnen",
"Must be smaller than the radius of the container": "Muss kleiner sein als der Radius des Behälters",
"How far the brush is dragged over the rim to knock the drop off, once on each side (mm). Typically the same or slightly larger than the radius of the petri dish. Classic containers only: a modern bay wipes the brush on its own stairs, so nothing reads this.":
  "Wie weit der Pinsel über den Rand gezogen wird, um den Tropfen abzustreifen, je einmal auf jeder Seite (mm). Üblicherweise so groß wie der Radius der Petrischale oder wenig größer. Nur bei klassischen Behältern: Eine moderne Kammer streift den Pinsel an ihren eigenen Stufen ab, also liest dies dort niemand.",
"Number of initial color mixing cycles. 0 for plotter":
  "Anzahl der anfänglichen Anmischgänge. 0 beim Plotten",
"Speed settings for painting/drawing, fetching color (faster), and removing color drops":
  "Geschwindigkeiten für das Malen bzw. Zeichnen, das Farbholen (schneller) und das Abstreifen der Tropfen",
"Post-processes the generated G-code to apply backlash compensation by injecting specific corrective moves whenever the X or Y axis changes direction":
  "Bearbeitet die erzeugten Maschinensteuerbefehle nach und gleicht das Umkehrspiel aus, indem bei jedem Richtungswechsel der X- oder Y-Achse eigene Korrekturbewegungen eingefügt werden",
"Play in the X axis (mm), measured at the X0 end of the bed. Draw backlash.g with a pen and read the upright pairs of its two stations at that end against the X gauge. On Pinkograph this is the axis that changes across the bed: 1.9 mm here and 1.3 at the far end.":
  "Spiel der X-Achse (mm), gemessen am Ende X0 der Arbeitsfläche. Zeichnen Sie backlash.g mit einem Stift und lesen Sie die stehenden Paare seiner beiden Stationen an diesem Ende am X-Maßstab ab. Beim Pinkograph ist dies die Achse, die sich über die Arbeitsfläche hinweg ändert: 1,9 mm hier und 1,3 am fernen Ende.",
"Play in the X axis (mm) at the far end of X. Read the upright pairs of backlash.g's two stations at that end. Equal to Backlash X means one figure everywhere, which is what an even axis wants; where the two differ the compensation follows a straight line between them across the bed. X play that changes with X is the belt: what is lost at a reversal is the slack and the stretch of the length between the drive and the carriage, and that length is what changes.":
  "Spiel der X-Achse (mm) am fernen Ende von X. Lesen Sie die stehenden Paare der beiden Stationen von backlash.g an diesem Ende ab. Gleich dem Umkehrspiel X bedeutet überall derselbe Wert, was eine gleichmäßige Achse verlangt; unterscheiden sich die beiden, so folgt der Ausgleich einer Geraden zwischen ihnen über die Arbeitsfläche hinweg. Ändert sich das Spiel in X mit X, so liegt es am Riemen: verloren geht bei der Umkehr die Lose und die Dehnung des Stückes zwischen Antrieb und Schlitten, und eben dessen Länge ändert sich.",
"Play in the Y axis (mm), measured at the X0 end of the bed. Read the flat pairs of backlash.g's two stations at that end against the Y gauge. Pinkograph reads 1.3 mm here and 1.2 at the far end, which is near enough one figure.":
  "Spiel der Y-Achse (mm), gemessen am Ende X0 der Arbeitsfläche. Lesen Sie die liegenden Paare der beiden Stationen von backlash.g an diesem Ende am Y-Maßstab ab. Der Pinkograph zeigt hier 1,3 mm und 1,2 am fernen Ende, was nahezu ein einziger Wert ist.",
"Play in the Y axis (mm) at the far end of X. Read the flat pairs of backlash.g's two stations at that end. Two stations at one end that disagree mean the play depends on where the gantry stands along Y as well, which no pair of figures can describe: take the middle station's reading for both boxes. Y play that changes with X is the gantry beam twisting: it is driven from one side, so the far side arrives carrying whatever the beam has wound up. Equal figures mean one play everywhere.":
  "Spiel der Y-Achse (mm) am fernen Ende von X. Lesen Sie die liegenden Paare der beiden Stationen von backlash.g an diesem Ende ab. Weichen zwei Stationen an einem Ende voneinander ab, so hängt das Spiel auch davon ab, wo das Portal in Y steht, was kein Wertepaar beschreiben kann: Nehmen Sie dann den Wert der mittleren Station für beide Felder. Ändert sich das Spiel in Y mit X, so verwindet sich der Portalträger: er wird von einer Seite angetrieben, und die ferne Seite kommt mit dem an, was der Träger aufgedreht hat. Gleiche Werte bedeuten überall dasselbe Spiel.",
"Max brush width (mm) for Z-mapping": "Größte Pinselbreite (mm) für die Z-Zuordnung",
"Minimum skeleton path length in pixels": "Kürzeste Skelettbahn in Bildpunkten",
"Smoothing window size for path filtering": "Fensterbreite der Glättung beim Filtern der Bahnen",
"Travel distance in millimetres of painting before performing an automatic dip":
  "Gemalte Strecke in Millimetern, nach der selbsttätig nachgetaucht wird",
"Feed rate mm/min for painting moves": "Vorschub in mm/min für malende Bewegungen",
"Wipe radius in millimetres after dipping": "Abstreifradius in Millimetern nach dem Tauchen",
"Z height in millimetres used during wiping motion (before offset)":
  "Z-Höhe in Millimetern während des Abstreifens (vor dem Versatz)",
"Dip entry radius in millimetres": "Eintauchradius in Millimetern",
"Enable removal of drops via wiping": "Tropfen durch Abstreifen entfernen",
"Global Z offset added to all Z coordinates": "Globaler Z-Versatz, der auf alle Z-Koordinaten addiert wird",
"Safe Z for rapid moves (mm, before offset)": "Sichere Z-Höhe für Eilgänge (mm, vor dem Versatz)",
"Safe Z for dip moves (mm, before offset)": "Sichere Z-Höhe für Tauchfahrten (mm, vor dem Versatz)",

/* ------------------------------------------------ what the page says back */
"Choose a config to download first": "Wählen Sie zuerst eine Konfiguration zum Herunterladen",
"Loading options…": "Einstellungen werden geladen …",
"Upload failed": "Übertragung fehlgeschlagen",
"Generating…": "Wird berechnet …",
"Preparing…": "Wird vorbereitet …",
"Converting…": "Wird umgewandelt …",
"Separating…": "Wird zerlegt …",
"Starting…": "Wird gestartet …",
"No images selected": "Keine Bilder ausgewählt",
"set a width first": "setzen Sie zuerst eine Breite",
"Tracing, slicing and planning brush strokes.":
  "Konturen werden verfolgt, zerlegt und zu Pinselstrichen geplant.",
"Downloaded {file} ({size} KB).": "Heruntergeladen: {file} ({size} KB).",
"Ready: {file} ({size} KB). Preview below.": "Fertig: {file} ({size} KB). Vorschau unten.",
"The file is ready, but the preview could not be drawn: {error}":
  "Die Datei ist fertig, die Vorschau ließ sich aber nicht zeichnen: {error}",
"Download {file}": "{file} herunterladen",
"{size} KB": "{size} KB",
"no G0/G1 movement was found in that file":
  "in dieser Datei wurde keine G0/G1-Bewegung gefunden",
"images differ in aspect ratio — will use {tray} ({w}x{h})":
  "die Bilder haben verschiedene Seitenverhältnisse — es gilt {tray} ({w}×{h})",
"{w}x{h} mm from {tray} — narrowed from {asked} mm, the bed paints {max} mm tall":
  "{w}×{h} mm nach {tray} — von {asked} mm verschmälert, die Arbeitsfläche malt {max} mm hoch",
"height {height} mm, matching {tray}'s {w}x{h} px":
  "Höhe {height} mm, passend zu {w}×{h} px von {tray}",
"Choose a photo for a tray first": "Wählen Sie zuerst ein Foto für einen Behälter",
"Convert {tray}'s photo": "Das Foto von {tray} umwandeln",

/* the subject the segmentation found, and how it found it */
"Isolate {what}": "{what} freistellen",
"a person": "eine Person",
"{count} people": "{count} Personen",
"an animal": "ein Tier",
"a prominent object": "einen hervortretenden Gegenstand",
"found by {how}, covering {percent}% of the frame — the background becomes bare paper":
  "gefunden durch {how}, bedeckt {percent} % des Bildes — der Hintergrund wird blankes Papier",
"segmentation": "Segmentierung",
"saliency": "Auffälligkeit",
"upperbody": "Oberkörper",
"fullbody": "Ganzkörper",
"frontalface": "Gesicht von vorn",
"profileface": "Gesicht im Profil",
"{count} face(s)": "{count} Gesicht(er)",
"segmentation and {count} face(s)": "Segmentierung und {count} Gesicht(er)",
"segmentation, {percent}% animal": "Segmentierung, {percent} % Tier",

/* the preview's own numbers */
"painted": "gemalt",
"travel": "Leerfahrt",
"brush downs": "Pinselansätze",
"cup dips": "Tauchgänge",
"moves": "Bewegungen",
"rough time": "grobe Dauer",
"{n} min": "{n} Min.",
"{n} h": "{n} Std.",
"{percent}% of {n} moves": "{percent} % von {n} Bewegungen",
"painting": "Malen",
"in the cups": "in den Behältern",

/* macros */
"Generated {count} macros from the settings above.":
  "{count} Makros aus den obigen Einstellungen erzeugt.",
"{name} ({bytes} B)": "{name} ({bytes} B)",

/* to the machine */
"Set a hostname under Machine setup, Connection.":
  "Tragen Sie unter „Maschineneinrichtung“, „Verbindung“ einen Netzwerknamen ein.",
"This page is on https and {base} is not, so the browser will block the connection. Open the WebUI over http on the same network as the machine, or download the file and upload it yourself.":
  "Diese Seite liegt auf https, {base} nicht, daher unterbindet der Browser die Verbindung. Rufen Sie die Weboberfläche über http im selben Netz wie die Maschine auf, oder laden Sie die Datei herunter und übertragen Sie sie selbst.",
"This page is on https and {base} is not, so the browser will block the connection. Open the WebUI over http on the same network as the machine, or download the macros and upload them yourself.":
  "Diese Seite liegt auf https, {base} nicht, daher unterbindet der Browser die Verbindung. Rufen Sie die Weboberfläche über http im selben Netz wie die Maschine auf, oder laden Sie die Makros herunter und übertragen Sie sie selbst.",
"Sending {name} to {base}…": "{name} wird an {base} gesendet …",
"{name} sent to {base}. The reply is opaque, so check the machine's own file list to be sure.":
  "{name} an {base} gesendet. Die Antwort bleibt verdeckt, prüfen Sie daher zur Sicherheit die Dateiliste der Maschine.",
"{name} sent. Waiting {seconds}s for the card to catch up…":
  "{name} gesendet. {seconds} s Wartezeit, bis die Karte nachgekommen ist …",
"{name}: $SD/Run sent. The machine says: {said}":
  "{name}: $SD/Run gesendet. Die Maschine meldet: {said}",
"{name}: $SD/Run sent, but the machine said nothing back. Check it.":
  "{name}: $SD/Run gesendet, die Maschine meldete aber nichts zurück. Prüfen Sie sie.",
"Could not reach {base}: {error}. Check the hostname under Machine setup, Connection, and that this page and the machine are on the same network.":
  "{base} war nicht erreichbar: {error}. Prüfen Sie den Netzwerknamen unter „Maschineneinrichtung“, „Verbindung“ und dass diese Seite und die Maschine im selben Netz liegen.",
"the machine did not accept a websocket connection":
  "die Maschine nahm keine Websocket-Verbindung an",
"websocket refused": "Websocket abgewiesen",
"Sending {name} to {base} (flash)… ({sent}/{total})":
  "{name} wird an {base} gesendet (Flash-Speicher) … ({sent}/{total})",
"Sent {count} macros to {base}'s flash filesystem. The reply is opaque, so check the machine's own file list to be sure.":
  "{count} Makros an den Flash-Speicher von {base} gesendet. Die Antwort bleibt verdeckt, prüfen Sie daher zur Sicherheit die Dateiliste der Maschine.",
"{name} did not go: waiting and trying again ({go}/{tries})…":
  "{name} ging nicht durch: warten und noch einmal versuchen ({go}/{tries}) …",
"{base} stopped taking files at {name}: {error}. Sent {sent}/{total}, each tried {tries} times. Check the hostname under Machine setup, Connection, and that this page and the machine are on the same network — and if the ones that landed are the first few every time, the board's flash filesystem may be full: look at its file list and clear out what is not a macro.":
  "{base} nahm ab {name} keine Dateien mehr an: {error}. {sent}/{total} gesendet, jede {tries}-mal versucht. Prüfen Sie den Netzwerknamen unter „Maschineneinrichtung“, „Verbindung“ und dass diese Seite und die Maschine im selben Netz liegen — und wenn jedes Mal dieselben ersten Dateien ankommen, ist womöglich der Flash-Speicher der Platine voll: sehen Sie in deren Dateiliste nach und räumen Sie auf, was kein Makro ist.",

/* ---------------------------------------- fixed messages the server sends */
"No file supplied": "Keine Datei übergeben",
"No image supplied": "Kein Bild übergeben",
"Machine configs must be named *.conf": "Maschinenkonfigurationen müssen *.conf heißen",
"Config name may only contain letters, digits, dot, dash, underscore":
  "Der Name der Konfiguration darf nur Buchstaben, Ziffern, Punkt, Strich und Unterstrich enthalten",
"That JSON has no 'brushograph' section — not a machine config":
  "Dieses JSON hat keinen Abschnitt „brushograph“ — es ist keine Maschinenkonfiguration",
"No ink in any CMYK plate, and no tray pictures":
  "Keine Farbe auf irgendeiner CMYK-Platte und keine Bilder in den Behältern",
"bad config name": "ungültiger Name der Konfiguration",
"config not found": "Konfiguration nicht gefunden",
"bad host": "ungültiger Rechnername",
"bad config mode": "ungültige Art der Konfiguration",

},

/* ------------------------------------------------------------------ prose */
/* Keyed by data-i18n, because German will not keep the English word order
 * around the tags inside these. */
html: {

"brand-tagline":
  '<a href="https://wiki.sgmk-ssam.ch/wiki/Brushograph">Brušograf</a> Steuerbefehl-Generator' +
  '<span class="edition-note"> – Ausgabe\n' +
  '        <a href="https://wiki.sgmk-ssam.ch/wiki/Brushograph#Zweiter_Bruschologischer_Kongress,_Dresden,_7._-_12._September_2026"\n' +
  '           class="edition" aria-label="Zweiter Bruschologischer Kongress">𝖅𝖜𝖊𝖎𝖙𝖊𝖗 𝕭𝖗𝖚𝖘𝖈𝖍𝖔𝖑𝖔𝖌𝖎𝖘𝖈𝖍𝖊𝖗 𝕶𝖔𝖓𝖌𝖗𝖊𝖘𝖘</a></span>',

"setup-download-note":
  "Schreibt alles Obige samt den Fülleinstellungen wieder in eine <code>.conf</code> hinaus, " +
  "die Sie aufbewahren oder einer anderen Maschine übergeben können.",

/* --------------------------------------------------------- the about page */
"run-1": "Eine Maschinenkonfiguration (<code>.conf</code>) beschreibt die Maschine. Jede Einstellung darunter wird aus dieser Datei erzeugt.",
"run-2": "Sie laden je Behälter ein geschwelltes Bild hoch, gemalt in der Reihenfolge Gelb, Magenta, Cyan, dann Schwarz &mdash; oder eine einzelne Farbfotografie, die in CMYK zerlegt und zu ebendiesen Druckplatten geschwellt wird.",
"run-3": "Jedes Bild wird unmittelbar in Pinselstriche verwandelt. Jeder Farbpunkt wird mit seinem Abstand zum nächsten blanken Papier beschriftet, und eine um <i>d</i> eingerückte Kontur ist dann schlicht die Höhenlinie von &bdquo;mindestens <i>d</i> vom Rand entfernt&ldquo;. Eine konzentrische Füllung ist dasselbe bei einem halben Strich, anderthalb, zweieinhalb &hellip; also liefert eine einzige Abstandstransformation die ganze Füllung, und die Ringe werden nebeneinander gezeichnet, weil keiner vom anderen abhängt.",
"run-4": "<b>copicograf</b> verwandelt diese Striche in die Choreographie des Pinsels: Eintauchen in den Farbbehälter, Abstreifen des mitgeführten Tropfens, Auswaschen im Wasser und Nachtauchen alle paar hundert Millimeter.",

"note-kind": "Das Bild eines Behälters kann <b>bereits geschwellt</b> sein oder ein <b>Foto</b>. Ein Foto wird zunächst zum Holzschnitt, und der Holzschnitt besteht aus <b>Strichen</b>: langen, etwa eine Pinselbreite starken, die dort enger zusammenrücken, wo das Bild dunkler ist, und in den Lichtern ins Papier auslaufen. Sie folgen den Richtungen des Bildes selbst und legen sich um eine Form, wie es eine geschnittene Linie tut, statt als gerade Streifen oder Gitter darüberzuliegen. Nichts wird voll ausgefüllt — eine Fläche deckt der Pinsel, indem er in ihr im Kreis geht, und das sind hundert kurze Striche, wo ein Schatten gemeint war. Ein Foto wird zudem um eine Vierteldrehung gedreht, wenn seine lange Seite dann an der langen Seite der Unterlage liegt — auf einem breiten Bett malt das ein hochformatiges Bild um die Hälfte größer; ein bereits geschwelltes Bild wird so gemalt, wie es ankam. Sehen Sie sich das Ergebnis vor dem Lauf an.",
"note-cmyk": "Eine <b>Farbfotografie</b> unter „Bildvorlage“ wird mit demselben Papierprofil nach CMYK gewandelt, das auch der Rest dieses Bestandes benutzt; dann wird jeder Auszug an einer Farbschwelle zu einer zweitönigen Platte geschnitten. Diese Platten werden genau so verfolgt wie bereits geschwellte Bilder. Die vier Farbkarten sind beiseitegeräumt, solange eine Fotografie geladen ist, sodass die Platten allein aus ihr stammen; nehmen Sie die Fotografie fort, um sie von Hand hochzuladen. Töne unterhalb der Schwelle bleiben Papier, damit der Pinsel keine Lasur malen soll, die er nicht legen kann. Das Profil unterlegt dunkle Töne mit Cyan, Magenta und Gelb, wie es eine Druckmaschine tut, unter dem nachfolgenden Schwarz; diese drei werden überall dort ausgespart, wo Schwarz malt, was die Malarbeit einer Fotografie halbiert und nichts Sichtbares ändert. Ein Schalter neben der Farbschwelle malt die Unterlage dennoch, für Behälter außer Passer.",
"note-isolate": "Wird im Foto eine Person, ein Tier oder ein hervortretender Gegenstand erkannt, erscheint die Möglichkeit <b>Freistellen</b>. Sie schneidet das Motiv mit einem kleinen Segmentierungsnetz heraus (U&sup2;-Net, 4,4&nbsp;MB, beim ersten Start einmalig geladen und über OpenCV betrieben) und lässt den Hintergrund als blankes Papier zurück. Ohne das Modell weicht sie auf GrabCut aus, was schlechter ist, die Sache aber am Leben hält.",
"note-opening": "Der Eröffnungsablauf &mdash; anmischen, waschen, den Pinsel laden &mdash; gehört nicht zum Auftrag. Ein Auftrag beginnt mit dem zu malen, was bereits am Pinsel ist.",
"note-dip": "Die <b>Tauchtiefe</b> bestimmt, wie weit der Pinsel in einen Behälter fährt. Sie lag fest bei Z&nbsp;&minus;4, was tiefer ist, als eine flache Schale es braucht. Sie wird stets angeboten, auch von einer Konfiguration, die sie nicht erwähnt, ebenso die Einstellungen zum Umkehrspiel, die angehakt sind, sofern die Konfiguration nichts anderes sagt.",
"note-mix": "<b>Tauchspuren</b> gibt an, auf wie viele Stellen quer durch einen rechteckigen Behälter die Farbaufnahmen verteilt werden. Der Pinsel fährt an einer davon gerade hinab und streicht von dort die Stufen hinauf; die nächste Aufnahme nimmt eine andere. Die Farbe wird also dadurch gemischt, wo der Pinsel aufsetzt, und nicht durch Rühren, sobald er unten ist — ein seitlich durch abgesetzte Farbe gezogener Pinsel spreizt sich und streift dabei an der Farbe wieder ab, was der vorige Zug aufgenommen hat. Die Spuren liegen über den mittleren 70% des Behälters und werden in versetzter Reihenfolge angefahren, sodass aufeinanderfolgende Aufnahmen gegenüberliegende Enden bearbeiten. 1 setzt jede Aufnahme in die Mitte. Sie bleiben innerhalb des Verfahrwegs der Maschine, was bei einem Halter zählt, dessen breitester Behälter über einen Endschalter hinausragt.",
"note-backlash": "Die Vorschau zeigt die Bahn ohne Ausgleich des Umkehrspiels. Jene Korrekturbewegungen gelten dem Spiel der Maschine, und sie zu zeichnen würde das Bild unter Strichen begraben, die nicht darin vorkommen.",
"note-face": "Die <b>Gesichtsretusche</b>, angeboten sobald ein Gesicht gefunden wurde, gleicht das Licht über dem Gesicht aus und glättet die Haut vor der Umwandlung. Ein Holzschnitt hat zwei Töne, also fällt ein von einer Seite beleuchtetes Gesicht größtenteils auf die schwarze Seite und läuft zu einer einzigen vollen Form zusammen. Die Beleuchtung wird allein über der Haut geschätzt &mdash; bei etwa einem Achtel der Gesichtsbreite, und diese Einstellung entscheidet, wie viel Schatten weicht &mdash; und wieder herausgeteilt, was dunkle Züge verhältnismäßig dunkel hält; Augen, Brauen, Nasenlöcher und Lippen werden danach in voller Stärke zurückgesetzt. Gesichter findet ein kleiner neuronaler Sucher, sodass auch ein gedrehter oder gesenkter Kopf noch erkannt wird, mit den mitgelieferten Kaskaden von OpenCV als Rückfall. Berührt wird nur Haut &mdash; Haar, Brille, Kragen und Hintergrund behalten den Ton, den sie hatten.",
"note-thin": "Eine Form, die zu schmal für eine Kontur ist, bekommt stattdessen ihre Mittellinie gemalt, sodass jedes Band, jede Haarlinie und jede Rippe gezeichnet statt fallen gelassen wird.",
"note-zero-infill": "Ein <b>Fülllinienabstand von 0</b> malt nur Konturen. Für den Pinsel steht dann eine angenommene Strichbreite von 1&nbsp;mm ein, da die Konfiguration keine nennt.",
"note-names": "Dateien werden nach dem Bild und den benutzten Behältern benannt &mdash; <code>vali_letten_c1_infill.gcode</code> &mdash;, wobei die Behälter in der Reihenfolge gezählt werden, in der die Konfiguration sie nennt, mit dem Wasserbehälter als 0.",
"note-threshold": "Die Trennung zwischen Farbe und Papier wird je Bild gefunden statt fest vorgegeben, damit ein Druck auf cremefarbenem Papier nicht als ein einziger voller Block Farbe gelesen wird. Sie wird auf dem dunkelsten Farbauszug genommen, damit auch eine helle Farbe wie Gelb noch als Farbe zählt.",
"note-spacing": "<b>Setzen Sie <code>infill_line_distance</code> ungefähr auf die Breite, die Ihr Pinsel legt.</b> Es ist der Abstand zwischen den Fülllinien; ein Wert aus dem Stiftplotterbau wie 0,5&nbsp;mm malt dieselbe Fläche zehnfach. An einem Versuchsbild sank beim Übergang von 0,5&nbsp;mm auf 5&nbsp;mm die Zahl der Pinselhübe von 598 auf 103, die der Tauchgänge von 318 auf 74 und die gemalte Strecke von 23,8&nbsp;m auf 4,5&nbsp;m.",
"note-chaining": "Striche werden wieder aneinandergehängt, und Enden innerhalb von anderthalb Linienbreiten werden zu einer Schlangenlinie verbunden, damit der Pinsel so lange wie möglich unten bleibt. Weiter zu greifen bringt nichts: Der Pinsel muss ohnehin alle <code>paint_per_run</code> nachtauchen.",
"note-copicograf": "copicograf erkennt das Heben und Senken des Pinsels an zwei genauen Z-Zeilen, die nur <code>cura-slicer</code> ausgibt. Die Striche werden in ebendieser Form geschrieben, sodass <code>copicograf.py</code> selbst unberührt bleibt.",
"note-generator": "Konfigurationen, die einen anderen Generator als <code>copicograf</code> nennen, zeigen ihre Einstellungen hier an, lassen sich aber nicht bauen &mdash; jener Generator gehört nicht zu diesem Bestand.",
"note-marlin": "<code>M204</code>, <code>M203</code> und <code>M400</code> stammen aus den <code>moves</code>-Blöcken der Konfiguration und gibt es nur bei Marlin. Sie bleiben bei <b>Steuerungstyp: Marlin</b> erhalten und werden für GRBL und FluidNC entfernt, die bei einem unbekannten M-Befehl anhalten. Eine Konfiguration ohne Steuerungsabschnitt gilt als GRBL.",
"note-preamble": "Jede Datei beginnt mit <code>G90</code>/<code>G21</code>, dem gewöhnlichen Vorschub und einem Hub auf die sichere Z-Höhe der Konfiguration, bevor sich irgendetwas seitwärts bewegt &mdash; wo der letzte Auftrag den Pinsel gelassen hat, ist nicht bekannt.",
"note-load": "Der Pinsel wird vor dem ersten Strich jeder Farbe geladen. Jeder Behälter endet damit, den Pinsel zu waschen und im Wasser abzustellen &mdash; was ein Farbwechsel verlangt &mdash;, und nachgetaucht wird sonst erst, wenn <code>paint_per_run</code> gemalt worden ist, sodass jede Farbe früher damit begann, mit Wasser zu malen. Der Gang endet an dem Punkt, an dem das Malen dieser Farbe beginnt, und hinterlässt so keine eigene Spur.",
"note-change": "Ein Farbwechsel ist: den Pinsel dreimal im Wasser waschen, freiheben, die nächste Farbe fassen, den Tropfen abstreifen und zum ersten Strich fahren. Am Ende des Auftrags bleibt der Pinsel im Wasser stehen, damit er nicht mit Farbe darin trocknet, zwischen den Farben aber nicht &mdash; er steht dann schon über dem Wasser und geht als Nächstes ohnehin zur Farbe.",
"note-home": "<code>copicograf</code> gibt einmal nahe dem Anfang <code>G28 X Y</code> aus. Marlin fährt darauf heim; GRBL und FluidNC weisen die bloßen Achsenbuchstaben rundweg ab, daher wird die Zeile durch einen Kommentar ersetzt. Sie wird nicht zu <code>$H</code> umgeschrieben, was Endschalter verlangt &mdash; <b>fahren Sie die Maschine selbst heim oder setzen Sie sie auf Null, bevor Sie senden.</b>",

"themes": "Sechs, in der Fußzeile, von Ihrem Browser behalten: <b>Standard</b> folgt Ihrem System, <b>Dunkelmodus</b> bleibt dunkel, <b>Kokosnussmodus</b> ist Schale und Palme, <b>Pinkograph</b> trägt, was die FluidNC-Oberfläche der Maschine selbst trägt, Farben und alles, mit einem Schild, das flackert wie eine Neonröhre, <b>UwU</b> ist dasselbe Schild mit allen Lichtern an, und <b>𝕭𝖗𝖚𝖘𝖈𝖍𝖔𝖑𝖔𝖌𝖎𝖘𝖈𝖍𝖊𝖗 𝕶𝖔𝖓𝖌𝖗𝖊𝖘𝖘</b> bringt ein strenges schwarzweißes Druckbild, durchweg in UniFraktur gesetzt, und ist das einzige Erscheinungsbild, das Deutsch spricht: Solange es an ist, ist jedes Wort der Oberfläche übersetzt, und beim Abschalten steht wieder Englisch da. Keines der beiden Neonschilder bewegt sich, wenn Sie Ihrem System gesagt haben, Bewegung zu vermindern. Der Maschinenriss und die Vorschau der Maschinensteuerbefehle folgen dem Erscheinungsbild ebenfalls. Die Farben der Behälter tun das nie: Eine farbige Marke bedeutet immer Farbe in einem Behälter, was die Oberfläche auch trage. Schwarze Farbe ist die Ausnahme, und nur weil sie auf dunklem Papier das Papier wäre: Jedes Erscheinungsbild sagt, wie seine dunkelste Farbe aussieht, damit Schwarz sich noch als Farbe liest.",

},

/* -------------------------------------------- server text with a detail in it */
patterns: [
  ["^Server returned (\\d+)$", "Der Server antwortete mit $1"],
  ["^Could not load that config: (.*)$", "Diese Konfiguration ließ sich nicht laden: $1"],
  ["^Could not separate that image: (.*)$", "Dieses Bild ließ sich nicht zerlegen: $1"],
  ["^Could not convert that image: (.*)$", "Dieses Bild ließ sich nicht umwandeln: $1"],
  ["^Could not inspect that image: (.*)$", "Dieses Bild ließ sich nicht untersuchen: $1"],
  ["^Not valid JSON: (.*)$", "Kein gültiges JSON: $1"],
  ["^config not found: (.*)$", "Konfiguration nicht gefunden: $1"],
  ["^(.*) did not resolve: (.*)$", "$1 ließ sich nicht auflösen: $2"],
  ["^(.+): '(.*)' is not a number$", "$1: „$2“ ist keine Zahl"],
  ["^Tray (\\d+)$", "Behälter $1"],
  ["^Update (\\S+\\.conf)$", "$1 aktualisieren"],
  ["^(\\S+\\.conf) is no longer on the server, and a kept config leaves no copy in your session, so there is nothing here to write back\\. Pick another machine, or upload the file again to start from it\\.$",
   "$1 ist nicht mehr auf dem Server, und eine hinterlegte Konfiguration hinterlässt keine Abschrift in Ihrer Sitzung; es gibt hier also nichts zurückzuschreiben. Wählen Sie eine andere Maschine oder laden Sie die Datei erneut hoch, um von ihr auszugehen."],
  ["^(\\S+\\.conf) has been changed on the server since you loaded it\\. Pick it again from the machine list to see those changes; updating now would overwrite them\\.$",
   "$1 wurde auf dem Server geändert, seit Sie sie geladen haben. Wählen Sie sie erneut aus der Maschinenliste, um diese Änderungen zu sehen; jetzt zu aktualisieren würde sie überschreiben."],
  ["^A machine config is a few kilobytes; this one is (\\d+) KB, over the (\\d+) KB the server will keep\\.$",
   "Eine Maschinenkonfiguration umfasst wenige Kilobyte; diese hat $1 KB und liegt damit über den $2 KB, die der Server hinterlegt."],
  ["^The server already keeps (\\d+) machine configs, which is all it will hold\\. Use this one without keeping it, or ask whoever runs the server to clear some out\\.$",
   "Der Server hält bereits $1 Maschinenkonfigurationen, mehr fasst er nicht. Verwenden Sie diese, ohne sie zu hinterlegen, oder bitten Sie den Betreiber des Servers, einige zu entfernen."],
  ["^No free name for (.+) on the server\\.$", "Für $1 ist auf dem Server kein freier Name mehr."],
  ["^(.+) is no longer on the server\\. Uploaded configs are kept with your session and this one has expired — upload the file again, or pick one from the machine list\\.$",
   "$1 ist nicht mehr auf dem Server. Hochgeladene Konfigurationen gehören zu Ihrer Sitzung, und diese ist abgelaufen — laden Sie die Datei erneut hoch oder wählen Sie eine aus der Maschinenliste."],
],

};
