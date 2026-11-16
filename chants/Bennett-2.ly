\version "2.24.1"

\header{
  composer = \markup{\hspace #-33 \italic "George John Bennett (1863-1930)"}
  tagline=#f
}

global = {
  \key g \major
  \time 2/4
}


S_notes = \relative c'' {
  g2 | d'4 c | a2 \bar "||"
  g2 | b4 a | g fis8 e | d2 \bar "||"
  g2 | d'4 c | a2 \bar "||"
  b2 | g8 a b4 | a fis | g2 \bar "||"
}

A_notes = \relative c' {
  b2 | d4 e | d2 \bar "||"
  d2 | cis4 d | d cis | d2 \bar "||"
  b2 | d4 g | fis2 \bar "||"
  fis2 | e4 fis | e d | d2 \bar "||"
}

T_notes = \relative c' {
  g2 | g4 g | fis2 \bar "||"
  b2 | g4 a | b a8 g | fis2 \bar "||"
  g2 | b4 c | c2 \bar "||"
  b2 | b4 d | c a | b2 \bar "||"
}

B_notes = \relative c' {
  g2 | b,4 c | d2 \bar "||"
  e2 | e4 fis | g a | d,2 \bar "||"
  e2 | f4 e | e2 \bar "||"
  dis2 | e4 b | c d | g,2 \bar "||"
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
