\version "2.24.1"

\header{
  composer = \markup{\hspace #-33 \italic "Herbert Stanley Oakeley (1830-1903)"}
  tagline=#f
}

global = {
  \key f \major
  \time 2/4
}


S_notes = \relative c'' {
  a2 | g4 f | bes2 \bar "||"
  a2 | a4 g | f g | a2 \bar "||"
  a2 | a4 g | f2 \bar "||"
  f2 | f4 e | e d | c2 \bar "||"
  \break
  g'2^\markup \italic "The Gloria here." | c4 bes | a2 \bar "||"
  a2 | d4 c | bes a | bes2 \bar "||"
  bes2 | c4 g | a2 \bar "||"
  f2 | f4 bes | a g | f2 \bar "||"
}

A_notes = \relative c' {
  f2 | e4 f | f2 \bar "||"
  f2 | d4 d | c e | f2 \bar "||"
  e2 | d4 a | d2 \bar "||"
  d2 | d4 c | c b | c2 \bar "||"
  e2 | f4 g | c,2 \bar "||"
  f4. es8 | d4 g | g fis | g2 \bar "||"
  g2 | g4 e | f2 \bar "||"
  c4. es8 | d4 f | f e | f2 \bar "||"
}

T_notes = \relative c' {
  c2 | bes4 a | d2 \bar "||"
  c2 | c4 bes | a g8 c | c2 \bar "||"
  cis2 | d4 e | a,2 \bar "||"
  a2 | g4 g | g4. f8 | e2 \bar "||"
  c'4. bes8 | a4 g | f2 \bar "||"
  c'2 | bes4 es | d d | d2 \bar "||"
  d2 | c4 c | c2 \bar "||"
  c2 | bes4 d | c4. bes8 | a2 \bar "||"
}

B_notes = \relative c {
  f2 | f4 f | f2 \bar "||"
  f2 | bes,4 bes | c c | f,2 \bar "||"
  a2 | b4 cis | d2 \bar "||"
  d4. c8 | b4 c | g' g, | c2 \bar "||"
  c2 | d4 e | f2 \bar "||"
  f2 | bes4 c | d d, | g2 \bar "||"
  g4. f8 | e4 c | f2 \bar "||"
  a2 | bes4 g | c c, | f2 \bar "||"
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

% The book's note under the chant (Psalm 78)
\markup {
  \fill-line {
    \small \center-column {
      \line { Verses 1 to 4, 13 to 16, 21 to 28, 45 to 52, 73, and the Gloria, may be chanted \italic { in unison, } and full. }
      \line { Verses 5 to 12, 17 to 20, 29 to 44, 53 to 72, \italic { in harmony, } and antiphonally. }
    }
  }
}
