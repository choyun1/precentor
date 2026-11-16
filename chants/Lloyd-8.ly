\version "2.24.1"

\header{
  composer = \markup{\hspace #-33 \italic "Charles Harford Lloyd (1849-1919)"}
  tagline=#f
}

global = {
  \key g \major
  \time 2/4
}


S_notes = \relative c'' {
  g2 | b4 a | g2 \bar "||"
  fis2 | e4 fis | g a | fis2 \bar "||"
  a2 | d4 c | b2 \bar "||"
  b2 | a4 g | fis a | g2 \bar "||"
}

A_notes = \relative c'' {
  g2 | fis4 fis | e2 \bar "||"
  d2 | c4 c | d e | d2 \bar "||"
  fis2 | g4 a | d,2 \bar "||"
  f2 | e4 e | d d | d2 \bar "||"
}

T_notes = \relative c' {
  b2 | d4 c | b2 \bar "||"
  b2 | g4 a | g c | a2 \bar "||"
  d4. c8 | b4 a | g2 \bar "||"
  d'2 | c4. b8 | a4 c | b2 \bar "||"
}

B_notes = \relative c' {
  g2 | d4 d | e2 \bar "||"
  b2 | c4 a | b c | d2 \bar "||"
  d2 | e4 fis | g2 \bar "||"
  g2 | c4 c, | d d | g2 \bar "||"
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
