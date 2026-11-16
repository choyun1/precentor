\version "2.24.1"

\header{
  composer = \markup{\hspace #-33 \italic "Charles H. H. Parry (1848-1918)"}
  tagline=#f
}

global = {
  \key aes \major
  \time 2/4
}


S_notes = \relative c'' {
  as2 | g4 as | es2 \bar "||"
  f2 | bes4 bes | c f, | des'2 \bar "||"
  bes2 | as4 g | c2 \bar "||"
  c2 | bes4 f | \set Score.repeatCommands = #'((volta "")) es des | es2 \bar "||"
}

A_notes = \relative c' {
  es2 | des4 c | bes2 \bar "||"
  c2 | bes4 es | ges f | f2 \bar "||"
  f2 | f4 e | f2 \bar "||"
  es2 | des4 des | c as | bes2 \bar "||"
}

T_notes = \relative c' {
  c2 | bes4 as | g2 \bar "||"
  a2 | bes4 bes | bes a | bes2 \bar "||"
  f4. g8 | as4 des | c2 \bar "||"
  f,2 | f4 g | as as | as g \bar "||"
}

B_notes = \relative c {
  as2 | bes4 c8 des | es2 \bar "||"
  es2 | des4 ges | es f | bes2 \bar "||"
  des,2 | c4 bes | as2 \bar "||"
  a2 | bes4 bes | c f | es2 \bar "||"
}

% The Gloria's own ending, after the chant: printed, not played
S_amen = \relative c' {
  \set Score.repeatCommands = #`((volta #f) (volta ,#{ \markup \italic "for Gloria." #})) es4 des | es2
  \set Score.repeatCommands = #'((volta #f)) \bar "|."
}

A_amen = \relative c' {
  as4 des | des4 c
}

% "A - men." under the alto's Amen: the alto's 20 notes before it are skipped
amen_words = \lyricmode { \repeat unfold 20 { \skip 1 } A -- \skip 1 men. }

T_amen = \relative c' {
  as4 g | es2
}

B_amen = \relative c {
  c4 es | as,2
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
              \voiceOne { \S_notes \S_amen }
            >>
            \new Voice = "Alto" <<
              \voiceTwo { \A_notes \A_amen }
            >>
          >>
          \new Lyrics \with { \override LyricText.font-size = #-2 } \lyricsto "Alto" \amen_words
          \new Staff <<
            \global
            \clef "bass"
            \new Voice = "Tenor" <<
              \voiceOne { \T_notes \T_amen }
            >>
            \new Voice = "Bass" <<
              \voiceTwo { \B_notes \B_amen }
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
