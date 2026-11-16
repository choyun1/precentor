\version "2.24.1"

\header{
  composer = \markup{\hspace #-33 \italic "Thomas Rogers (1839-1899)"}
  tagline=#f
}

global = {
  \key ees \major
  \time 2/4
}


S_notes = \relative c'' {
  g2 | c4 bes | bes as \bar "||"
  bes2 | g4 c | bes a | g2 \bar "||"
  g2 | bes4 g | f e \bar "||"
  f2 | g4 as | f f | es2 \bar "||"
}

A_notes = \relative c' {
  es2 | es4 e | f2 \bar "||"
  f2 | es4 g | g fis | g2 \bar "||"
  es2 | d4 des | c2 \bar "||"
  c2 | e4 f8 es | es4 d | es2 \bar "||"
}

T_notes = \relative c' {
  bes2 | as4 bes | c2 \bar "||"
  bes2 | bes4 es | d4. c8 | bes2 \bar "||"
  bes2 | bes4 bes | as g \bar "||"
  as2 | bes4 c | bes4. as8 | g2 \bar "||"
}

B_notes = \relative c {
  es2 | as4 g | f2 \bar "||"
  d2 | es4 c | d d | g,2 \bar "||"
  es'2 | bes4 bes | c2 \bar "||"
  <as \tweak X-offset #2.1 \tweak font-size #-4 as'>2 | <g \tweak font-size #-4 g'>4 <f \tweak font-size #-4 f'> | bes bes | es2 \bar "||"
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
