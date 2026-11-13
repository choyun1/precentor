\version "2.24.1"

\header{
  composer = \markup{\hspace #-46.5 \italic "William Knyvett (1779-1856); after Handel"}
  tagline=#f
}

global = {
  \key f \major
  \time 2/4
}


S_notes = \relative g' {
  f2 | a4 g | bes2 \bar "||"
  a2 | d4 c | c b | c2 | \bar "||"
  f,2 | d4 g | f e \bar "||"
  c'2 | a4 f | f e | f2 | \bar "||"
}

A_notes = \relative c' {
  c2 | c4 c | f2 \bar "||"
  f2 | d8 e f4 | e d | e2 | \bar "||"
  c2 | bes4 d | c2 \bar "||"
  g'2 | f4 d | c c | c2 | \bar "||"
}

T_notes = \relative a {
  a2 | c4 c | bes2 \bar "||"
  c2 | f,4 f | g g | g2 | \bar "||"
  f2 | f4 bes | a g \bar "||"
  c2 | c4 bes | a g | a2 | \bar "||"
}

B_notes =  \relative c {
  f2 | f4 e | d2 \bar "||"
  c2 | bes4 a | g g | c2 | \bar "||"
  a2 | bes4 g | c2 \bar "||"
  e2 | f4 bes, | c c | f2 | \bar "||"
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