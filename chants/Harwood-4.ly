\version "2.24.1"

\header{
  composer = \markup{\hspace #-33 \italic "Basil Harwood (1859-1949)"}
  tagline=#f
}

global = {
  \key g \major
  \time 2/4
}


S_notes = \relative c'' {
  g2 | d4 g | b2 \bar "||"
  a2 | fis4 g | c a | b2 \bar "||"
}

A_notes = \relative c' {
  d2 | d4 e | fis2 \bar "||"
  e2 | d4 b | c d | d2 \bar "||"
}

T_notes = \relative c' {
  b2 | b4 b | d2 \bar "||"
  c2 | a4 g | e fis | g2 \bar "||"
}

B_notes = \relative c' {
  g2 | b4 e, | b2 \bar "||"
  c2 | d4 e | a, d | g,2 \bar "||"
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
