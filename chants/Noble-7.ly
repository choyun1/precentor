\version "2.24.1"

\header{
  composer = \markup{\hspace #-33 \italic "Thomas Tertius Noble (1867-1953)"}
  tagline=#f
}

global = {
  \key d \major
  \time 2/4
}


S_notes = \relative c'' {
  a2 | a4 a | a2 \bar "||"
  a2 | d4 e, | b' a8 g | fis2 \bar "||"
}

A_notes = \relative c'' {
  a2 | gis4 g | fis2 \bar "||"
  cis2 | d4 d | g fis8 e | d2 \bar "||"
}

T_notes = \relative c' {
  a2 | b4 cis | d2 \bar "||"
  a2 | a4 b | d cis | a2 \bar "||"
}

B_notes = \relative c' {
  a2 | a4 a | a2 \bar "||"
  g2 | fis4 g | e a, | d2 \bar "||"
}

% Words the book prints between the staves (Unison, Harmony): on one line, printed only
words = {
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
          \new Dynamics \with { \override TextScript.font-size = #-1.5 \override VerticalAxisGroup.nonstaff-relatedstaff-spacing.padding = #2 } \words
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
