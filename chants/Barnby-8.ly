\version "2.24.1"

\header{
  composer = \markup{\hspace #-33 \italic "Joseph Barnby (1838-1896)"}
  tagline=#f
}

global = {
  \key d \major
  \time 2/4
}


S_notes = \relative c' {
  fis2 | g4 fis | e2 \bar "||"
  g2 | a4 g | fis gis | a2 \bar "||"
  a2 | b4 a | g2 \bar "||"
  fis2 | e4 d | d cis | d2 \bar "||"
}

A_notes = \relative c' {
  d2 | e4 d | cis2 \bar "||"
  e2 | e4 cis | d d | cis2 \bar "||"
  d2 | fis4 fis | e2 \bar "||"
  cis2 | b4 b | a a | a2 \bar "||"
}

T_notes = \relative c' {
  a2 | a4 a | a2 \bar "||"
  b2 | a4 a | a d, | e2 \bar "||"
  fis2 | d'4 c | b2 \bar "||"
  ais2 | b4 g | fis e | fis2 \bar "||"
}

B_notes = \relative c {
  d2 | cis4 d | a2 \bar "||"
  e'2 | cis4 a | d b | a2 \bar "||"
  d2 | d4 dis | e2 \bar "||"
  fis2 | g4 g, | a a | d2 \bar "||"
}

% Use markup to center the chant on the page
\markup {
  \fill-line {
    \score {  % centered
      <<
        \new ChoirStaff <<
          \new Staff <<
            \global
            \clef "treble"
            \new Voice = "Soprano" <<
              \voiceOne \S_notes
            >>
            \new Voice = "Alto" <<
              \voiceTwo \A_notes
            >>
          >>
          \new Staff <<
            \global
            \clef "bass"
            \new Voice = "Tenor" <<
              \voiceOne \T_notes
            >>
            \new Voice = "Bass" <<
              \voiceTwo \B_notes
            >>
          >>
        >>
      >>

      \layout {
        \context {
          \Staff
          \remove "Time_signature_engraver"
        }
      }
    }  % End score
  }
}  % End markup
