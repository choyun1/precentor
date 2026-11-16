\version "2.24.1"

\header{
  composer = \markup{\hspace #-33 \italic "Edward Cuthbert Bairstow (1874-1946)"}
  tagline=#f
}

global = {
  \key c \major
  \time 2/4
}


S_notes = \relative c'' {
  g2 | a4 e | g2 \bar "||"
  g2 | e4 g8 a | b4 b | b2 \bar "||"
  c2 | b4 e | a,2 \bar "||"
  g2 | c4 f, | e8 f g4 | c,2 \bar "||"
}

A_notes = \relative c' {
  <\tweak font-size #-3 e \tweak font-size #-3 c>2 | <\tweak font-size #-3 e \tweak font-size #-3 c>4 <\tweak font-size #-3 a,>4 | <\tweak font-size #-3 b>2 \bar "||"
  e2 | e4 d | e4 dis | e2 \bar "||"
  e2 | e4 e | d2 \bar "||"
  d2 | c4 c | c4 b | c2 \bar "||"
}

T_notes = \relative c' {
  g2 | a4 e | g2 \bar "||"
  d'2 | c4 d8 c | b4 a | g2 \bar "||"
  a2 | b4 cis | d2 \bar "||"
  b2 | g4 a | g4 f | e2 \bar "||"
}

B_notes = \relative c {
  <\tweak font-size #-3 c>2 | <\tweak font-size #-3 a>4 <\tweak font-size #-3 c>4 | <\tweak font-size #-3 e>2 \bar "||"
  b'2 | c4 b8 a | g4 fis | e2 \bar "||"
  a2 | gis4 g | fis2 \bar "||"
  f2 | e4 d | g4 g, | c2 \bar "||"
}

% Words the book prints between the staves (Unison, Harmony): on one line, printed only
words = {
  s2*3-\markup \italic "Unison." \bar "||"
  s2*4-\markup \italic "Harmony." \bar "||"
  s2*3 \bar "||"
  s2*4 \bar "||"
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
          \new Dynamics \with { \override TextScript.font-size = #-1.5 \override TextScript.extra-offset = #'(-2.5 . 0) \override VerticalAxisGroup.nonstaff-relatedstaff-spacing.padding = #2 } \words
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
