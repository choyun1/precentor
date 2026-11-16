\version "2.24.1"

\header{
  composer = \markup{\hspace #-33 \italic "Charles John May"}
  tagline=#f
}

global = {
  \key aes \major
  \time 2/4
}


S_notes = \relative c'' {
  as2 | as4 es | c'2 \bar "||"
  f,4. g8 | as4 c | c bes8 as | bes2 \bar "||"
  bes2 | bes4 f | des'2 \bar "||"
  bes2 | es4 as, | bes c8 bes | as2 \bar "||"
}

A_notes = \relative c' {
  c4. des8 | es4 des | <c \tweak font-size #-3 es>2 \bar "||"
  des2 | es4 es | es d | es2 \bar "||"
  des4. es8 | f4 es | <des \tweak font-size #-3 f>2 \bar "||"
  es2 | es4 f | f g | as2 \bar "||"
}

T_notes = \relative c {
  es2 | es4 f8 g | as2 \bar "||"
  as2 | es4 as | as f | g2 \bar "||"
  f2 | f4 g8 a | bes2 \bar "||"
  g2 | as4 c | f4 es8 des | c2 \bar "||"
}

B_notes = \relative c {
  as4. bes8 | c4 bes | as2 \bar "||"
  des2 | c4 as | f' bes, | es2 \bar "||"
  bes4. c8 | des4 c | bes2 \bar "||"
  es2 | c4 f | des es | as2 \bar "||"
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
