\version "2.24.1"

\header{
  composer = \markup{\hspace #-33 \italic "Charles Harford Lloyd (1849-1919)"}
  tagline=#f
}

global = {
  \key e \major
  \time 2/4
}


S_notes = \relative c'' {
  b2 | cis4 dis | e2 \bar "||"
  e,2 | fis4 gis | a b | gis2 \bar "||"
  gis2 | a4 b | cis2 \bar "||"
  dis,2 | e4 fis | gis fis | e2 \bar "||"
}

A_notes = \relative c'' {
  gis2 | gis4 fis | e2 \bar "||"
  cis2 | e4 e | fis fis | e2 \bar "||"
  e2 | e4 d | cis2 \bar "||"
  b2 | b4 e | e dis | e2 \bar "||"
}

T_notes = \relative c' {
  b2 | b4 a | gis2 \bar "||"
  e'2 | cis4 b | cis b | b2 \bar "||"
  b2 | a4 gis | a2 \bar "||"
  fis2 | b4 cis | b a | gis2 \bar "||"
}

B_notes = \relative c {
  e2 | b4 b | cis2 \bar "||"
  cis'2 | a4 gis | fis dis | e2 \bar "||"
  d2 | cis4 b | a2 \bar "||"
  a2 | gis4 a | b b | e2 \bar "||"
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
