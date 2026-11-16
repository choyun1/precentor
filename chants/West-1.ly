\version "2.24.1"

\header{
  composer = \markup{\hspace #-33 \italic "John Ebenezer West (1863-1929)"}
  tagline=#f
}

global = {
  \key a \major
  \time 2/4
}


S_notes = \relative c'' {
  a2 | gis8 a b4 | e,2 \bar "||"
  e2 | cis'4 b | a4 gis8 fis | gis2 \bar "||"
  b2 | ais8 b cis4 | fis,2 \bar "||"
  fis2 | d'4 cis | b4 a8 gis | a2 \bar "||"
}

A_notes = \relative c' {
  e2 | d4 d | d2 \bar "||"
  cis2 | e4 e | e4 dis | e2 \bar "||"
  fis2 | e4 e | e2 \bar "||"
  d2 | d4 e | fis4 e | e2 \bar "||"
}

T_notes = \relative c' {
  a2 | e4 fis | b2 \bar "||"
  a2 | a4 b | cis4 b | b2 \bar "||"
  b2 | fis4 gis | cis2 \bar "||"
  b2 | gis4 a | d4 b | cis2 \bar "||"
}

B_notes = \relative c {
  cis2 | b4 a | gis2 \bar "||"
  a2 | a'4 gis | fis4 b, | e2 \bar "||"
  d2 | cis4 b | ais2 \bar "||"
  b2 | b4 cis | d4 e | a,2 \bar "||"
}

% Words the book prints between the staves (Unison, Harmony): on one line, printed only
words = {
  s2*3-\markup \italic "Unison." \bar "||"
  s2*4-\markup \italic "Harmony." \bar "||"
  s2*3-\markup \italic "Unison." \bar "||"
  s2*4-\markup \italic "Harmony." \bar "||"
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
          \new Dynamics \with { \override TextScript.font-size = #-1.5 \override TextScript.extra-offset = #'(-4.5 . 0) \override VerticalAxisGroup.nonstaff-relatedstaff-spacing.padding = #2 } \words
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
