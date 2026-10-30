# Original setup reference for SHRED TECH. Sections are grouped by component, not by
# execution order; the order of operations comes from the setup flow tool.

SETUP_REFERENCE = """
=== SHRED TECH Setup Reference ===

--- TARGET SPECS AT A GLANCE ---
Neck relief (gap at 6th fret):   0.010" (light touch) to 0.012" (hard attack)
Action at 12th fret, low E:      4/64" (1.6mm)
Action at 12th fret, high e:     3/64" (1.2mm)
Radius gauge position:           about 1/4" in front of the saddles
Truss rod increments:            1/8 turn at a time, retune between moves

Pickup height starting points (string-to-pickup with strings held down at the last fret):
  Strat, all positions     3/32" bass side, 1/16" treble side
  Humbucker                1/16" bridge, 3/32" neck
  J/P-Bass                 3/32" both sides
  Telecaster               no single standard; published figures vary widely. Start near
                           3/32" bass / 1/16" treble and adjust by ear.

--- GROUND RULES ---
- Measure only on a guitar wearing new strings, tuned to pitch, held in playing position.
- Neck relief comes first. Every other measurement depends on it.
- Anything involving a file (nut slots, Tune-O-Matic saddles) is permanent. Remove material
  in tiny amounts and re-measure constantly.
- Before starting: record the fretboard radius, tighten loose hardware, polish the frets, and
  clean the board. Oil unfinished rosewood or ebony lightly; leave maple dry.

--- NECK RELIEF ---
What you measure: the gap between the string and the 6th fret when the string is pinned at
both ends. Capo the 1st fret and press the low E at the 12th (or fret the 12th with your
other hand), then slide a feeler gauge under the string at the 6th fret.
Reading it:
  Gauge slides in with room to spare -> neck has too much forward bow; tighten the truss rod
                                         (clockwise).
  Gauge is gripped or string rises off it -> neck is bowed backward; loosen the rod
                                         (counter-clockwise).
  Light drag on the gauge -> relief is in range.
Small moves, then wait. Wood needs time to take a new shape, so give the neck up to half an
hour before trusting a final reading.

--- ACTION ON ADJUSTABLE-SADDLE BRIDGES (Strat, Tele, hardtail, non-Floyd tremolos) ---
Measure from the top of the 12th fret to the bottom of the string.
Dial in the low E and high e saddles first to the table values; they become reference points
for the radius work on the four middle strings. Each saddle has two height screws: clockwise
raises, counter-clockwise lowers, and the pair should stay even.

--- ACTION ON TUNE-O-MATIC BRIDGES ---
The whole bridge rides on two posts. Turn the thumbwheels together to raise or lower it,
keeping them matched unless you are deliberately offsetting for a skewed neck.
On this bridge, shape the saddle slots to the radius first, then set overall height.

--- RADIUS (STRING ARC) ---
Purpose: make the curve of the strings follow the curve of the fretboard so every string
clears the frets by a similar amount.
  Adjustable saddles: rest the correct radius gauge across the strings, near the saddles.
  Raise or lower the A, D, G and B saddles until every string just touches the gauge.
  Tune-O-Matic: lay the gauge over the saddles and file slots down to match. The tallest
  saddles get filed first. Slope each slot downward toward the tailpiece (the back), so the
  string leaves from the front edge of the saddle; round that edge slightly so it can't
  cut the string. Press lightly and check after every few strokes. Wound strings sit happily in a slightly tighter slot than
  plain ones.

--- NUT SLOT HEIGHT ---
Check: a feeler gauge pushed between the open string and the first fret.
  String rests on the gauge, open chords ring cleanly -> good.
  String rests on the gauge but open strings buzz -> slot is cut too deep. Fill and
    recut it, or install a new nut.
  Gauge won't touch the string -> slot is too high. Deepen it with a properly sized nut file.
Filing notes: match the file to the string (no more than .003" wider than the string; e.g.
a .049" file for a .046" string). Angle the file toward the headstock so the string
leaves the nut at its front edge. A handful of gentle strokes, clean out the slot, then
re-check. Rubbing a pencil across the slot first reveals where you've cut.
Finish by lubricating the nut slots and saddle contact points (graphite or a purpose-made
nut lubricant) so strings return to pitch after bends.

--- INTONATION ---
For each string: tune accurately, then compare the note at the 12th fret with the open
string.
  Fretted note reads flat -> the speaking length is too long; slide the saddle toward the
    neck.
  Fretted note reads sharp -> the speaking length is too short; slide the saddle toward the
    tailpiece.
The string's pitch shifts when you move a saddle, so retune before each new comparison.
Stop when the two notes agree.
Players who live in the upper register can verify higher up the neck as well.
On three-saddle Telecaster bridges, each saddle shares two strings, so settle for the best
overall result and give priority to the wound string.

--- PICKUP HEIGHT ---
Use the table above. Closer pickups give a louder, thicker output but their magnets tug on
the strings, which can make notes warble and tuning drift. Farther pickups sound weaker and
thinner. The goal is even volume from string to string and a sensible balance between
pickups. Finish with the bridge pickup since it shapes the overall blend most.
"""
