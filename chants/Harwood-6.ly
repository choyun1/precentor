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
  g2 | a4 b8 c | b2 \bar "||"
  g2 | a4 c | b g | g fis \bar "||"
  g2 | b4 cis | d2 \bar "||"
  g,2 | e'4 d8 c | b4 a | g2 \bar "||"
}

A_notes = \relative c' {
  d2 | d4 d | d2 \bar "||"
  e2 | d4 fis | g e | d2 \bar "||"
  d2 | g4 fis8 e | d2 \bar "||"
  d2 | c4 e | g fis | g2 \bar "||"
}

T_notes = \relative c' {
  b2 | a4 fis | g2 \bar "||"
  b2 | a4 a | d c | b a \bar "||"
  b2 | g4 a8 g | fis2 \bar "||"
  g2 | g4 c | d4. c8 | b2 \bar "||"
}

B_notes = \relative c' {
  g2 | fis4 d | g2 \bar "||"
  e2 | c4 a | b c | d2 \bar "||"
  g2 | e4 a, | d2 \bar "||"
  b2 | c4 a | d d | g,2 \bar "||"
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
