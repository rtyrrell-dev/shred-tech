"""
18 test cases for the SHRED TECH eval harness.

Distribution:
  6  setup
  4  troubleshooting_mechanical
  3  troubleshooting_electrical
  3  gear
  2  ambiguous  (coordinator should ask a clarifying question, not transfer immediately)

expected_specialist is the agent name that should produce the final response:
  SetupAgent / TroubleshootingAgent / GearRecommendationAgent / shred_tech (coordinator)
"""

TEST_CASES = [
    # ── SETUP (6) ──────────────────────────────────────────────────────────────
    {
        "id": "setup-01",
        "query": (
            "I just got my first electric guitar and the strings are really hard to press down. "
            "Is that normal or is something wrong with it?"
        ),
        "expected_specialist": "SetupAgent",
        "category": "setup",
    },
    {
        "id": "setup-02",
        "query": "I need to do a complete setup on my Stratocaster from scratch. Where do I start?",
        "expected_specialist": "SetupAgent",
        "category": "setup",
    },
    {
        "id": "setup-03",
        "query": (
            "I have a Les Paul with a Tune-O-Matic bridge. "
            "How do I match the string radius to the fretboard?"
        ),
        "expected_specialist": "SetupAgent",
        "category": "setup",
    },
    {
        "id": "setup-04",
        "query": (
            "My guitar has a Floyd Rose tremolo and I have no idea how to set it up. "
            "I've never adjusted one before. What's the process?"
        ),
        "expected_specialist": "SetupAgent",
        "category": "setup",
    },
    {
        "id": "setup-05",
        "query": (
            "What string gauge should I use for Drop C tuning on a 25.5 inch scale guitar? "
            "I play heavy rhythm and downtuned riffs."
        ),
        "expected_specialist": "SetupAgent",
        "category": "setup",
    },
    {
        "id": "setup-06",
        "query": (
            "I've set the outer saddles to 4/64\" bass and 3/64\" treble at the 12th fret. "
            "After adjusting the inner saddles, my G string sits about 0.5mm above the radius "
            "gauge no matter how I adjust it. Is this a neck issue or should I compensate at "
            "the saddle?"
        ),
        "expected_specialist": "SetupAgent",
        "category": "setup",
    },
    # ── TROUBLESHOOTING — MECHANICAL (4) ───────────────────────────────────────
    {
        "id": "trouble-mech-01",
        "query": (
            "My low E string buzzes around the 3rd to 5th fret. "
            "It wasn't doing this before — started after I changed strings."
        ),
        "expected_specialist": "TroubleshootingAgent",
        "category": "troubleshooting_mechanical",
    },
    {
        "id": "trouble-mech-02",
        "query": (
            "Every time I bend my G string up a whole step it goes really sharp "
            "and takes ages to come back down to pitch."
        ),
        "expected_specialist": "TroubleshootingAgent",
        "category": "troubleshooting_mechanical",
    },
    {
        "id": "trouble-mech-03",
        "query": (
            "There's a completely dead note on the 7th fret of my D string — "
            "barely any sound and zero sustain. Other frets on that string are fine."
        ),
        "expected_specialist": "TroubleshootingAgent",
        "category": "troubleshooting_mechanical",
    },
    {
        "id": "trouble-mech-04",
        "query": (
            "My action is way too high but I've already lowered the bridge saddles "
            "as far as they'll physically go. What else could be causing this?"
        ),
        "expected_specialist": "TroubleshootingAgent",
        "category": "troubleshooting_mechanical",
    },
    # ── TROUBLESHOOTING — ELECTRICAL (3) ───────────────────────────────────────
    {
        "id": "trouble-elec-01",
        "query": (
            "My Stratocaster hums really badly on the neck pickup and bridge pickup positions, "
            "but positions 2 and 4 are dead quiet. What's going on?"
        ),
        "expected_specialist": "TroubleshootingAgent",
        "category": "troubleshooting_electrical",
    },
    {
        "id": "trouble-elec-02",
        "query": (
            "There's a loud crackling and scratching sound every time I turn the volume knob "
            "on my guitar. It's been getting worse over the past few weeks."
        ),
        "expected_specialist": "TroubleshootingAgent",
        "category": "troubleshooting_electrical",
    },
    {
        "id": "trouble-elec-03",
        "query": (
            "My neck pickup suddenly stopped working completely — no signal at all. "
            "Bridge pickup is perfectly fine. What should I check first?"
        ),
        "expected_specialist": "TroubleshootingAgent",
        "category": "troubleshooting_electrical",
    },
    # ── GEAR RECOMMENDATIONS (3) ────────────────────────────────────────────────
    {
        "id": "gear-01",
        "query": (
            "My stock pickups sound really muddy and lack definition for blues. "
            "Should I upgrade them and if so what would you recommend?"
        ),
        "expected_specialist": "GearRecommendationAgent",
        "category": "gear",
    },
    {
        "id": "gear-02",
        "query": (
            "What amp would you recommend for classic rock and blues tones "
            "with a budget of around $500?"
        ),
        "expected_specialist": "GearRecommendationAgent",
        "category": "gear",
    },
    {
        "id": "gear-03",
        "query": (
            "Is it worth upgrading to locking tuners to fix my tuning stability issues, "
            "or should I look at other solutions first?"
        ),
        "expected_specialist": "GearRecommendationAgent",
        "category": "gear",
    },
    # ── AMBIGUOUS (2) — coordinator should ask ONE clarifying question ──────────
    {
        "id": "ambiguous-01",
        "query": "My action feels off.",
        "expected_specialist": "shred_tech",
        "category": "ambiguous",
    },
    {
        "id": "ambiguous-02",
        "query": "I'm having issues with my intonation.",
        "expected_specialist": "shred_tech",
        "category": "ambiguous",
    },
]
