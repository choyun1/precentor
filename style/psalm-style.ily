%% psalm-style.ily — every typographic decision for pointed psalm texts lives here.
%% Change a value below and every psalm and Sunday leaflet picks it up on the next build.

%% ---------- typeface ----------
#(define psalm-font "EBG Medium")               % chosen; "EBG SemiBold" is the heavier alternative
#(define psalm-symbol-font (string-append psalm-font " Ext"))  % same weight, holds the dagger
#(define psalm-font-dir "fonts")               % folder holding the font files, relative to this style file

%% ---------- page layout (distances in staff spaces, roughly the width of an "n") ----------
#(define left-indent 16)                       % blank space at the left of every line
#(define number-column 3)                      % verse numbers are right-aligned in a column this wide
#(define number-gap 1.4)                       % space between the verse number and the text
#(define flex-indent 1)                        % further lines of the first half (before the *)
#(define second-indent 3)                      % second half of the verse
#(define wrap-indent 14)                       % a long line that runs over (+ in the text file)
#(define title-size 4)                         % font-size step for "Psalm 23"
#(define title-gap 4)                          % space between the title and the Latin incipit
#(define smallcaps-size -1.5)                  % size of the small capitals in LORD, GOD
#(define dagger-gap 0.35)                      % space between the dagger and the verse number

%% ---------- verse layout ----------
#(define verse-number-size -1)                 % font-size step for verse numbers (0 = same as text)
#(define line-spacing 3.55)                    % baseline to baseline within a verse (LilyPond default 3.0)
#(define verse-gap 0.55)                       % blank space between verses, in text lines (was 1.0 = \null)
#(define verse-padding 2.9)                    % blank space between verses when each verse is its own block

%% ---------- bar line (ACP short raised stroke) ----------
#(define bar-bottom 0.78)                      % where the stroke starts, above baseline (staff spaces)
#(define bar-height 0.92)                      % stroke length
#(define bar-thickness 0.13)
#(define bar-gap-after 0.22)                   % space between stroke and the syllable it marks
#(define bar-position 'centered)               % 'centered = middle of the space between words, 'tight = against the next word
#(define word-gap 0.6)                         % LilyPond's normal space between words (for centring)
#(define bar-space 1.12)                       % total space between two words when a centred bar sits between them
#(define bar-gap-inword 0.21)                  % space either side of a bar inside a split word (re'vives)
#(define dash-gap 0.45)                        % extra space after the dash that fills an empty bar

%% ---------- group bracket (syllables sharing one note) ----------
#(define bracket-clearance 0.30)               % gap between the top of tall letters (d, l, h) and the bracket line
#(define bracket-inset 0.28)                   % how far each end stops short of the group's edges (about half a letter)
#(define bracket-end 'round)                   % 'round = curled ends, 'splay = short outward hooks, 'square = ACP-like
#(define bracket-hook 0.20)                    % depth of the ends
#(define bracket-thickness 0.085)

%% ---------- held syllable (one syllable over both notes of a bar) ----------
#(define held-style 'dots)                     % 'dots (ACP diaeresis over vowel), 'line (bar over vowel), 'bold

%% ---------- dagger (verse sung to the second half of a double chant again) ----------
#(define dagger-raise 0.25)
#(define dagger-size -1)

%% =====================================================================
%% implementation — no need to edit below this line
%% =====================================================================
#(define psalm-style-dir (dirname (car (ly:input-file-line-char-column (*location*)))))
#(ly:font-config-add-directory
   (if (absolute-file-name? psalm-font-dir) psalm-font-dir
       (string-append psalm-style-dir "/" psalm-font-dir)))
\paper { property-defaults.fonts.serif = #psalm-font }

#(define-markup-command (acpbar layout props) ()
   "Bar between words: drawn back into the preceding word space when centred."
   (let* ((centred (eq? bar-position 'centered))
          (x (if centred (- (/ bar-space 2) word-gap) 0))
          (right (if centred (- bar-space word-gap) bar-gap-after)))
     (ly:make-stencil
       `(draw-line ,bar-thickness ,x ,bar-bottom ,x ,(+ bar-bottom bar-height))
       (cons 0 right)
       (cons bar-bottom (+ bar-bottom bar-height)))))

#(define-markup-command (acpbarin layout props) ()
   "Bar inside a split word, with a small equal gap on each side."
   (let ((g bar-gap-inword))
     (ly:make-stencil
       `(draw-line ,bar-thickness ,g ,bar-bottom ,g ,(+ bar-bottom bar-height))
       (cons 0 (* 2 g))
       (cons bar-bottom (+ bar-bottom bar-height)))))

#(define-markup-command (grp layout props arg) (markup?)
   "Bracket over syllables sharing one note: inset from the ends, a fixed small gap above ascender height."
   (let* ((st (interpret-markup layout props arg))
          (x (ly:stencil-extent st X))
          (asc (cdr (ly:stencil-extent (interpret-markup layout props "dlh") Y)))
          (x0 (+ (car x) bracket-inset)) (x1 (- (cdr x) bracket-inset))
          (t (+ asc bracket-clearance)) (h bracket-hook) (k bracket-thickness)
          (path
            (case bracket-end
              ((round)  (list 'moveto x0 (- t h)
                              'curveto x0 (- t (* 0.3 h)) (+ x0 (* 0.3 h)) t (+ x0 h) t
                              'lineto (- x1 h) t
                              'curveto (- x1 (* 0.3 h)) t x1 (- t (* 0.3 h)) x1 (- t h)))
              ((splay)  (list 'moveto (- x0 (* 0.6 h)) (- t h) 'lineto x0 t
                              'lineto x1 t 'lineto (+ x1 (* 0.6 h)) (- t h)))
              (else     (list 'moveto x0 (- t h) 'lineto x0 t 'lineto x1 t 'lineto x1 (- t h))))))
     (ly:stencil-add st (make-path-stencil path k 1 1 #f))))

%% \held "N" "a" "me's" : held syllable, marked over its vowel
#(define-markup-command (held layout props pre vow post) (markup? markup? markup?)
   (let* ((v (interpret-markup layout props vow))
          (vx (ly:stencil-extent v X))
          (vy (ly:stencil-extent v Y))
          (cx (/ (+ (car vx) (cdr vx)) 2))
          (top (+ (cdr vy) 0.28))
          (mark
            (case held-style
              ((dots) (ly:stencil-add
                        (ly:stencil-translate (make-circle-stencil 0.085 0 #t) (cons (- cx 0.2) top))
                        (ly:stencil-translate (make-circle-stencil 0.085 0 #t) (cons (+ cx 0.2) top))))
              ((line) (make-line-stencil 0.09 (+ (car vx) 0.05) top (- (cdr vx) 0.05) top))
              (else empty-stencil)))
          (v2 (ly:stencil-add v mark)))
     (interpret-markup layout props
       (if (eq? held-style 'bold)
           (markup #:bold #:concat (pre vow post))
           (markup #:concat (pre #:stencil v2 post))))))

#(define-markup-command (vnum layout props n) (markup?)
   (interpret-markup layout props (markup #:fontsize verse-number-size n)))

#(define-markup-command (versegap layout props) ()
   (interpret-markup layout props (markup #:vspace verse-gap)))

%% dagger replaces each file's own \cross definition
#(define-markup-command (psalmdagger layout props) ()
   (interpret-markup layout props
     (markup #:hspace -2.4 #:raise dagger-raise #:fontsize dagger-size
             #:override (cons 'font-name psalm-symbol-font) "†")))
cross = \markup \psalmdagger

%% small capitals for LORD / GOD: \concat { "L" \scs "ORD" }
#(define-markup-command (scs layout props arg) (markup?)
   (interpret-markup layout props (markup #:fontsize smallcaps-size arg)))

%% blank space of a given kind, used at the start of continuation lines
#(define (indent-of kind)
   (+ left-indent number-column number-gap
      (case kind ((flex) flex-indent) ((second) second-indent) ((wrap) wrap-indent) (else 0))))
#(define-markup-command (ind layout props kind) (symbol?)
   (ly:make-stencil "" (cons 0 (- (indent-of kind) word-gap)) '(0 . 0)))

%% start of a verse: indent, optional dagger, verse number right-aligned in its column
#(define-markup-command (vstart layout props num dagger) (markup? boolean?)
   (let* ((n (interpret-markup layout props (markup #:fontsize verse-number-size num)))
          (w (interval-length (ly:stencil-extent n X)))
          (x (+ left-indent (- number-column w)))
          (st (ly:stencil-translate-axis n x X))
          (st (if dagger
                  (let* ((d (interpret-markup layout props
                              (markup #:raise dagger-raise #:fontsize dagger-size
                                      #:override (cons 'font-name psalm-symbol-font) "†")))
                         (dw (interval-length (ly:stencil-extent d X))))
                    (ly:stencil-add st (ly:stencil-translate-axis d (- x dagger-gap dw) X)))
                  st)))
     (ly:make-stencil (ly:stencil-expr st)
                      (cons 0 (- (indent-of 'first) word-gap))
                      (ly:stencil-extent st Y))))

%% title line: "Psalm 23    Dominus regit me"
#(define-markup-command (psalmtitle layout props title latin) (markup? markup?)
   (interpret-markup layout props
     (markup #:concat (#:hspace (+ left-indent 2) #:fontsize title-size title
                       #:hspace title-gap #:italic latin))))

\paper {
  markup-markup-spacing = #`((basic-distance . 0) (minimum-distance . 0) (padding . ,verse-padding))
  score-markup-spacing = #'((basic-distance . 2) (padding . 1.5))
  markup-system-spacing = #'((basic-distance . 2) (padding . 1.5))
}

%% dash filling an empty bar, with its own breathing room before the next bar line
#(define-markup-command (emptybar layout props) ()
   (interpret-markup layout props (markup #:concat ("—" #:hspace dash-gap))))

%% ---------- plainchant psalm tones ----------
#(define tonebar-height 1.25)                  % the mark where the cadence begins (taller than the Anglican bar)
#(define slur-depth 0.32)                      % depth of the slur under a syllable sung to several notes
#(define slur-thickness 0.09)

#(define-markup-command (tonebar layout props) ()
   "Mark before the first syllable of the cadence."
   (ly:make-stencil
     `(draw-line ,bar-thickness 0.15 ,(- bar-bottom 0.25) 0.15 ,(+ bar-bottom tonebar-height))
     (cons 0 0.55) (cons (- bar-bottom 0.25) (+ bar-bottom tonebar-height))))

#(define-markup-command (slurunder layout props arg) (markup?)
   "A small slur under a syllable sung to more than one note."
   (let* ((st (interpret-markup layout props arg))
          (x (ly:stencil-extent st X))
          (x0 (+ (car x) 0.1)) (x1 (- (cdr x) 0.1))
          (y -0.45) (d slur-depth))
     (ly:stencil-add st
       (make-path-stencil
         (list 'moveto x0 y 'curveto (+ x0 (* 0.25 (- x1 x0))) (- y d) (- x1 (* 0.25 (- x1 x0))) (- y d) x1 y)
         slur-thickness 1 1 #f))))

#(define-markup-command (flexmark layout props) ()
   (interpret-markup layout props
     (markup #:raise dagger-raise #:fontsize dagger-size #:override (cons 'font-name psalm-symbol-font) "†")))
