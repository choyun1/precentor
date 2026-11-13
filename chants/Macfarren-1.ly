\version "2.24.1"

\header{
  composer = \markup{\hspace #-60 \italic "George A. Macfarren (1813-1887)"}
  tagline=#f
}

global = {
  \key a \minor
  \time 2/4
}


S_notes = \relative g' {
  c2 | b4 gis | a2 \bar "||"
  e2 | f4 d | e e | e2 | \bar "||"
}

A_notes = \relative c' {
  e2 | e4 e | c2 \bar "||"
  e2 | d4 d | b b | c2 | \bar "||"
}

T_notes = \relative a {
  a2 | b4 b | a2 \bar "||"
  a2 | a4 a | a gis | a2 | \bar "||"
}

B_notes =  \relative c {
  a'2 | gis4 e | f2 \bar "||"
  c2 | d4 f | e e | a,2 | \bar "||"
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