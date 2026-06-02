from google.adk.tools import FunctionTool


def get_setup_flow(bridge_type: str) -> dict:
    """Returns the correct ordered setup step list based on bridge type.

    Args:
        bridge_type: Type of bridge on the guitar. Accepted values: strat, tele, hardtail,
            non-floyd-trem, tune-o-matic, tom, gibson, epiphone, floyd-rose, bigsby, acoustic.
    """
    bridge_lower = bridge_type.lower().replace(" ", "-").replace("_", "-")

    path_a_bridges = {"strat", "tele", "hardtail", "non-floyd-trem", "hardtail-trem"}
    path_b_bridges = {"tune-o-matic", "tom", "gibson", "epiphone"}
    special_cases = {"floyd-rose", "bigsby", "acoustic"}

    if bridge_lower in path_a_bridges or any(b in bridge_lower for b in path_a_bridges):
        return {
            "path": "A",
            "bridge_type": bridge_type,
            "description": "Adjustable individual saddles",
            "steps": [
                "1. Pre-Setup — remove strings, clean/condition, tighten hardware, install fresh strings",
                "2. Truss Rod — set neck relief with capo at 1st, feeler gauge at 6th, fretted at 12th",
                "3. Action — set outer two saddles (low E and high e) at 12th fret",
                "4. Radius — adjust inner saddles to match fretboard radius gauge",
                "5. Nut Height — check and file each slot to correct height",
                "6. Intonation — tune string, compare 12th fret fretted vs open, move saddle accordingly",
                "7. Pickup Height — press to last fret, measure distance to pickup top",
            ],
            "notes": [
                "Action is set BEFORE radius on this path — set outer saddles first as anchors.",
                "Nut filing is irreversible — go slowly, check after every few strokes.",
            ],
        }

    if bridge_lower in path_b_bridges or any(b in bridge_lower for b in path_b_bridges):
        return {
            "path": "B",
            "bridge_type": bridge_type,
            "description": "Fixed-radius bridge (Tune-O-Matic / TOM)",
            "steps": [
                "1. Pre-Setup — remove strings, clean/condition, tighten hardware, install fresh strings",
                "2. Truss Rod — set neck relief with capo at 1st, feeler gauge at 6th, fretted at 12th",
                "3. Radius — file TOM saddle slots to match fretboard radius gauge",
                "4. Action — raise/lower entire bridge via post thumbwheels",
                "5. Nut Height — check and file each slot to correct height",
                "6. Intonation — tune string, compare 12th fret fretted vs open, move saddle accordingly",
                "7. Pickup Height — press to last fret, measure distance to pickup top",
            ],
            "notes": [
                "Radius is set BEFORE action on this path — filing saddles changes action, so radius goes first.",
                "TOM saddle filing is irreversible — file the highest saddles first, go slowly.",
                "If this is a three-saddle Tele, compromise intonation between string pairs.",
            ],
        }

    if bridge_lower in special_cases or any(b in bridge_lower for b in special_cases):
        special_info = {
            "floyd-rose": {
                "name": "Floyd Rose / locking tremolo",
                "notes": [
                    "Floyd Rose setups require a specific sequence that differs from both Path A and B.",
                    "The locking nut must be unlocked for all adjustments and locked only at the end.",
                    "Spring tension and bridge float angle must be balanced against string tension — changes to one affect the other.",
                    "Recommended: level the bridge parallel to the body first (typically 3–4 springs at 45°), then proceed with truss rod, action, nut, intonation using fine tuners.",
                    "This is outside the standard KISS guide scope — I'll draw on broader Floyd Rose setup knowledge to walk you through it.",
                ],
            },
            "bigsby": {
                "name": "Bigsby vibrato",
                "notes": [
                    "Bigsby setups follow Path B (TOM bridge is standard pairing) for bridge and radius steps.",
                    "The Bigsby unit itself doesn't require height adjustment — focus on the bridge.",
                    "Lubricate all contact points (nut, bridge pins, roller bar) thoroughly — Bigsby is sensitive to friction.",
                    "This is outside the standard KISS guide scope — I'll supplement with broader knowledge.",
                ],
            },
            "acoustic": {
                "name": "Acoustic guitar",
                "notes": [
                    "Acoustic setup differs significantly from electric — saddle and nut compensation, neck angle, and bridge pin fit all matter.",
                    "There is no truss rod on many classical guitars; on steel-string acoustics, adjustment range is limited.",
                    "Saddle material (bone, tusq, plastic) affects tone and sustain significantly.",
                    "This is outside the standard KISS guide scope — I'll draw on broader acoustic setup knowledge.",
                ],
            },
        }
        for key, info in special_info.items():
            if key in bridge_lower:
                return {
                    "path": "special",
                    "bridge_type": bridge_type,
                    "description": info["name"],
                    "notes": info["notes"],
                }

    return {
        "path": "unknown",
        "bridge_type": bridge_type,
        "description": "Unrecognized bridge type",
        "notes": [
            f"Bridge type '{bridge_type}' wasn't recognized.",
            "Please describe the bridge in more detail (e.g. 'synchronized tremolo like a Strat', 'fixed hardtail', 'Tune-O-Matic like a Les Paul').",
        ],
    }


def diagnose_issue(symptom: str) -> dict:
    """Maps mechanical guitar symptoms to likely causes and setup steps to revisit.

    Args:
        symptom: The mechanical problem being experienced. Accepted values: buzzing,
            tuning-instability, sharp-after-bends, flat-after-bends, intonation-off,
            high-action, dead-note, weak-output, uneven-output.
    """
    symptom_lower = symptom.lower().replace(" ", "-").replace("_", "-")

    diagnoses = {
        "buzzing": {
            "likely_causes": [
                "Neck relief too low (back-bow or insufficient forward bow)",
                "Action too low at the nut (open string buzz on low frets)",
                "Action too low at the saddles (buzz on higher frets)",
                "High frets (one or more frets taller than neighbors — needs fret leveling)",
                "Loose hardware vibrating (tuner screws, strap buttons, truss rod nut)",
            ],
            "diagnostic_questions": [
                "Does the buzz happen on open strings, fretted notes, or both?",
                "Which frets trigger the buzz — low frets (1–5), mid frets (5–12), high frets (12+), or everywhere?",
                "Does it buzz on all strings or just specific strings?",
                "Did you recently change string gauge or tuning?",
            ],
            "steps_to_revisit": ["Truss Rod", "Action", "Nut Height"],
            "additional_notes": "If buzz is isolated to one or two frets and not fixed by relief/action, suspect a high fret — run a straightedge along the frets to identify the culprit.",
        },
        "tuning-instability": {
            "likely_causes": [
                "Nut slots too narrow or not lubricated — strings binding at nut",
                "Strings not properly stretched in",
                "Saddle contact points not lubricated (especially on trem bridges)",
                "Worn or low-quality tuning machines",
                "String wound incorrectly on tuner post (too many wraps, or wraps crossing)",
                "Nut slot angle incorrect (not angled toward headstock)",
            ],
            "diagnostic_questions": [
                "Does the guitar go out of tune sharp or flat after use?",
                "Does it happen after bending strings?",
                "Do you use a tremolo / whammy bar?",
                "How old are the strings, and were they stretched in when installed?",
            ],
            "steps_to_revisit": ["Nut Height", "Pre-Setup"],
            "additional_notes": "Lubricate nut slots and saddle contact points with Nut Sauce, graphite, or Big Bends. If using a trem, check all pivot points. Locking nuts or locking tuners eliminate most nut-related tuning issues.",
        },
        "sharp-after-bends": {
            "likely_causes": [
                "Nut slots too narrow — string binds going sharp during bend and doesn't return to pitch",
                "Saddle friction (especially on trem bridges)",
                "String not lubricated at contact points",
            ],
            "diagnostic_questions": [
                "Does the string go sharp temporarily after a bend, then slowly creep back?",
                "Or does it stay sharp?",
                "Does this happen on specific strings or all of them?",
            ],
            "steps_to_revisit": ["Nut Height"],
            "additional_notes": "Classic symptom of a binding nut slot. Lightly widen the slot and lubricate. The string should drop back to pitch immediately after a bend.",
        },
        "flat-after-bends": {
            "likely_causes": [
                "Nut slot too wide — string slipping at nut",
                "Tuning machine slipping — worn gear or loose tuner button screw",
                "String wound improperly — slipping at the post",
            ],
            "diagnostic_questions": [
                "Does the string go flat and stay flat, or does it creep back?",
                "When did this start — with new strings, or gradually?",
            ],
            "steps_to_revisit": ["Nut Height", "Pre-Setup"],
            "additional_notes": "If nut slot is too wide, the slot needs to be filled (baking soda + thin CA glue) and re-filed, or the nut replaced. Check tuner button screws are snug.",
        },
        "intonation-off": {
            "likely_causes": [
                "Saddles in wrong position — intonation not set",
                "Nut slot too high — fretted note goes sharp everywhere (nut acts like a capo)",
                "Old or worn strings — windings expand unevenly",
                "Neck relief incorrect — affects intonation readings",
                "Incorrect string gauge for scale length",
            ],
            "diagnostic_questions": [
                "Is the 12th fret fretted note sharp or flat compared to the open string?",
                "Is intonation off on all strings or just some?",
                "When did you last change strings?",
                "Have you recently changed string gauge or tuning?",
            ],
            "steps_to_revisit": ["Truss Rod", "Nut Height", "Intonation"],
            "additional_notes": "Always check truss rod and nut before intonation — both affect the readings. Set intonation last, and use fresh strings.",
        },
        "high-action": {
            "likely_causes": [
                "Saddles set too high",
                "Too much neck relief (too much forward bow)",
                "Nut slots too high",
                "Neck angle issue (uncommon — needs a shim or neck reset)",
            ],
            "diagnostic_questions": [
                "Is the action high everywhere, or mainly at the nut (low frets) or high frets?",
                "Does fretting at the 1st fret feel much harder than fretting at the 5th?",
                "Has the neck been removed recently?",
            ],
            "steps_to_revisit": ["Truss Rod", "Action", "Nut Height"],
            "additional_notes": "High action at only the low frets usually means the nut slots are too high. High action everywhere is typically saddles or neck relief.",
        },
        "dead-note": {
            "likely_causes": [
                "High fret next to the fretted position killing the note (sitar-like sound or no sustain)",
                "Neck pocket loose — body resonance escaping",
                "Faulty string (internal break or manufacturing defect)",
                "Nut slot issue on open strings",
            ],
            "diagnostic_questions": [
                "Which fret and string is the dead note on?",
                "Is there any sustain at all, or does the note die immediately?",
                "Does it sound sitar-like or just dead?",
                "Have you tried a new string on that course?",
            ],
            "steps_to_revisit": ["Truss Rod", "Action"],
            "additional_notes": "A dead note that appears only on one fret usually points to a high neighboring fret. Use a straightedge or fret rocker to find the high fret. If the note is dead on multiple frets, try a fresh string first.",
        },
        "weak-output": {
            "likely_causes": [
                "Pickup too far from strings",
                "Faulty pickup (broken coil wire — needs professional rewinding)",
                "Wiring issue (see electrical diagnosis)",
                "Volume or tone pot failing",
            ],
            "diagnostic_questions": [
                "Is the output weak on all pickups or just one?",
                "Has pickup height been checked recently?",
                "Is the signal clean but quiet, or is it also thin/tinny sounding?",
            ],
            "steps_to_revisit": ["Pickup Height"],
            "additional_notes": "Start with pickup height before investigating electronics. A pickup even 1–2mm too far from the strings can cause noticeably weaker output.",
        },
        "uneven-output": {
            "likely_causes": [
                "Pickup height not matched across strings (tilt off from fretboard radius)",
                "One or more pole pieces not adjusted to string height (on adjustable-pole pickups)",
                "One pickup much closer or farther than others (pickup-to-pickup imbalance)",
            ],
            "diagnostic_questions": [
                "Is the unevenness between individual strings, or between pickups (neck vs bridge)?",
                "Which strings are louder or quieter?",
                "Is the pickup angled, or are the pole pieces visibly uneven?",
            ],
            "steps_to_revisit": ["Pickup Height"],
            "additional_notes": "For string-to-string imbalance, adjust pole pieces (on pickups that have them) before moving the whole pickup. Tilt the pickup slightly if one side is consistently louder.",
        },
    }

    for key, info in diagnoses.items():
        if key in symptom_lower or symptom_lower in key:
            return {"symptom": symptom, **info}

    return {
        "symptom": symptom,
        "likely_causes": ["Symptom not recognized in standard diagnostic list."],
        "diagnostic_questions": [
            "Can you describe the issue in more detail?",
            "When does it happen (open strings, specific frets, bending, picking hard)?",
            "Does it affect all strings or specific ones?",
        ],
        "steps_to_revisit": ["Full setup review recommended"],
        "additional_notes": f"'{symptom}' wasn't matched to a standard symptom. Please describe what you're experiencing in more detail.",
    }


def diagnose_electrical_issue(symptom: str) -> dict:
    """Maps electrical guitar symptoms to likely causes and recommended fixes.

    Draws on general electronics knowledge — this is outside KISS guide scope.

    Args:
        symptom: The electrical problem being experienced. Accepted values: hum,
            single-coil-hum, crackling, dead-signal, volume-drop, switch-noise, pot-noise,
            intermittent-signal, pickup-out.
    """
    symptom_lower = symptom.lower().replace(" ", "-").replace("_", "-")

    diagnoses = {
        "hum": {
            "likely_causes": [
                "Ground loop or missing ground connection in the control cavity",
                "Unshielded control cavity or pickup cavities — acting as an antenna",
                "Cold or cracked solder joint on ground wire",
                "Bridge/tailpiece not properly grounded to circuit ground",
                "Single-coil pickups (inherent 60-cycle hum — see single-coil-hum)",
            ],
            "diagnostic_questions": [
                "Does the hum change when you touch metal parts of the guitar (strings, bridge, jack)?",
                "Does it hum on all pickup positions or just some?",
                "Is it a steady 60Hz buzz or a higher-frequency interference?",
                "Does the hum disappear or reduce when you touch the strings?",
            ],
            "recommended_fixes": [
                "Check that the bridge ground wire is intact and properly soldered",
                "Test by touching the output jack sleeve — if hum stops, you have a ground issue",
                "Shield the control cavity and pickup routes with conductive shielding tape or conductive paint, connecting all shielding to ground",
                "Inspect all solder joints under magnification for cracks or cold joints",
                "Ensure all ground connections converge at one point (star grounding)",
            ],
            "outside_kiss_scope": True,
        },
        "single-coil-hum": {
            "likely_causes": [
                "Normal 60-cycle hum inherent to single-coil pickup design (not a fault)",
                "Missing or degraded shielding in cavities",
                "Nearby electrical interference (fluorescent lights, dimmer switches, CRT monitors, phone chargers)",
                "Poor or missing star grounding",
                "Faulty or missing ground on one coil of a stacked humbucker",
            ],
            "diagnostic_questions": [
                "Does the hum change when you move or rotate the guitar?",
                "Does it change near different electrical equipment?",
                "Is it present on all single-coil positions, or just neck, middle, or bridge?",
                "Do positions 2 and 4 (hum-canceling) on a Strat have less hum?",
            ],
            "recommended_fixes": [
                "Shielding the cavities with copper tape (all pieces connected, all connected to ground) is the most effective fix",
                "Stacked humbuckers or noiseless pickups (Kinman, Lace, Suhr) eliminate hum entirely while preserving single-coil tone",
                "Move away from interference sources when playing",
                "A noise gate pedal can manage hum in a live rig without modifying the guitar",
            ],
            "outside_kiss_scope": True,
        },
        "crackling": {
            "likely_causes": [
                "Dirty or oxidized potentiometer (pot) — most common cause of crackling when turning knobs",
                "Loose output jack — jack nut loose, causing intermittent contact",
                "Cold or cracked solder joint flexing with temperature/movement",
                "Oxidized pickup selector switch contacts",
                "Loose control cavity cover making intermittent contact with shielding",
            ],
            "diagnostic_questions": [
                "Does the crackle happen when you turn a specific knob, or randomly?",
                "Does wiggling the output jack cable reproduce the crackle?",
                "Is it worse in cold weather or after the guitar warms up?",
                "Does it happen when flipping the pickup selector?",
            ],
            "recommended_fixes": [
                "Spray DeoxIT D5 into the pot shaft and rotate the pot back and forth 20–30 times — clears oxidation on most pots",
                "Tighten the output jack nut with a 1/2\" socket wrench (hold the jack from inside to prevent twisting)",
                "Spray DeoxIT on pickup selector contact points and work the switch back and forth",
                "Inspect and reflow any suspect solder joints — look for dull, grainy, or cracked surfaces",
                "If pot cleaning doesn't fix it, replace the pot (CTS 250K or 500K are standard quality options)",
            ],
            "outside_kiss_scope": True,
        },
        "dead-signal": {
            "likely_causes": [
                "Output jack wiring disconnected or broken",
                "Volume pot wiper disconnected (open circuit)",
                "Pickup selector switch not making contact on the selected position",
                "Broken pickup coil wire (open circuit in pickup)",
                "Broken cable (test with a known-good cable first)",
            ],
            "diagnostic_questions": [
                "Have you confirmed the cable and amp are working with another guitar?",
                "Is there any signal at all, or completely silent?",
                "Did it stop suddenly or fade out over time?",
                "Does tapping the pickup with a screwdriver produce any signal in the amp?",
            ],
            "recommended_fixes": [
                "Test with a known-good cable and amp first — rule out external causes",
                "Tap each pickup with a steel screwdriver tip while plugged in — a working pickup produces a thud through the amp",
                "Check output jack wiring — inspect the tip and sleeve contacts for loose or broken wires",
                "Trace the signal path: pickup → selector → volume pot → output jack",
                "Use a multimeter in continuity mode to test each component in the signal chain",
            ],
            "outside_kiss_scope": True,
        },
        "volume-drop": {
            "likely_causes": [
                "Volume pot value wrong for pickup type (250K vs 500K) — loading down the pickup",
                "Failing capacitor on tone circuit (leaky cap bleeds signal to ground)",
                "High-resistance cold solder joint in signal path",
                "Pickup too far from strings (mechanical — check pickup height first)",
                "Treble bleed mod missing — volume drop seems to kill highs too",
            ],
            "diagnostic_questions": [
                "Is the drop across all pickups or just one?",
                "Does the volume drop at a specific knob position, or at all positions?",
                "Did it happen suddenly or gradually?",
                "Is the tone also darker/thinner than expected?",
            ],
            "recommended_fixes": [
                "Check pickup height first — it's the most common cause of output weakness",
                "Verify pot value matches the pickup: single coils typically use 250K, humbuckers 500K; mixing these affects tone and apparent volume",
                "Test by bypassing the tone pot to rule out a leaky capacitor",
                "Reflow all solder joints in the signal path",
                "Consider a treble bleed mod (150pF capacitor + 100K resistor) if volume taper seems to lose highs early",
            ],
            "outside_kiss_scope": True,
        },
        "switch-noise": {
            "likely_causes": [
                "Oxidized or dirty switch contacts",
                "Worn switch contacts no longer making solid contact",
                "Loose switch mounting",
                "Ground loop through switch body",
            ],
            "diagnostic_questions": [
                "Does the noise happen only when flipping the switch, or does it persist after?",
                "Is it a pop, crackle, or hum?",
                "How old is the guitar / has the switch ever been replaced?",
            ],
            "recommended_fixes": [
                "Spray DeoxIT D5 into the switch mechanism and work it back and forth 20–30 times",
                "If cleaning doesn't work, replace the switch — CRL 5-way and Switchcraft 3-way are reliable standards",
                "Ensure the switch body is grounded if it's a metal-body switch",
                "Tighten the switch mounting nut",
            ],
            "outside_kiss_scope": True,
        },
        "pot-noise": {
            "likely_causes": [
                "Oxidized pot tracks — very common on older guitars or guitars stored in humidity",
                "Worn carbon track from heavy use",
                "Wrong pot taper for the application (audio vs linear taper behavior difference)",
            ],
            "diagnostic_questions": [
                "Which pot is noisy — volume, tone, or both?",
                "Is it noisy throughout the sweep or only in a specific position?",
                "Has the guitar been stored without being played for a long time?",
            ],
            "recommended_fixes": [
                "DeoxIT D5 — spray into the pot shaft opening, rotate full sweep 20–30 times, repeat",
                "If noise persists: replace the pot. CTS 250K (single coils) or CTS 500K (humbuckers) are the standard",
                "Consider Bourns or Alpha pots as budget alternatives; avoid no-name pots",
                "Check that the pot value matches the pickup type — mismatched values affect taper and frequency response",
            ],
            "outside_kiss_scope": True,
        },
        "intermittent-signal": {
            "likely_causes": [
                "Loose output jack — most common cause of signal cutting in and out",
                "Cold solder joint flexing with cable movement",
                "Cracked wire insulation making intermittent contact",
                "Loose pickup selector switch internals",
                "Volume pot with a worn or open spot in the carbon track",
            ],
            "diagnostic_questions": [
                "Does the signal cut out when you move the cable at the guitar end?",
                "Does it cut out when you move the guitar body (suggesting an internal wire flexing)?",
                "Does it happen at a specific volume or tone setting?",
                "Does wiggling the pickup selector switch affect it?",
            ],
            "recommended_fixes": [
                "Start with the output jack — tighten the nut and inspect the jack contacts for proper spring tension",
                "Flex wires inside the cavity while plugged in to find intermittent cold joints",
                "Inspect all wire runs for pinched insulation or cracked conductors",
                "Reflow all solder joints that look dull, grainy, or cracked",
                "A proper Switchcraft or Neutrik output jack with fresh solder joints fixes 80% of intermittent signal issues",
            ],
            "outside_kiss_scope": True,
        },
        "pickup-out": {
            "likely_causes": [
                "Broken coil wire inside the pickup (open circuit) — usually requires rewinding or replacement",
                "Cold or broken solder joint where pickup leads connect to the circuit",
                "Pickup selector switch not making contact on the affected position",
                "Coil tap wire grounded incorrectly (on coil-split pickups)",
                "Faulty pickup selector (only routes signal on some positions)",
            ],
            "diagnostic_questions": [
                "Which pickup is not working? Is it only in certain switch positions?",
                "Did it stop working suddenly?",
                "Does tapping the silent pickup with a steel screwdriver produce any sound?",
                "Do other switch positions work correctly?",
            ],
            "recommended_fixes": [
                "Test the pickup by tapping it with a screwdriver — a thud through the amp means the coil is intact",
                "Check the selector switch — use a multimeter in continuity mode to verify it routes signal on the affected position",
                "Trace and reflow the pickup lead solder joints at the selector switch and/or volume pot",
                "If the coil is open (no thud, infinite resistance on multimeter between leads), the pickup needs rewinding or replacement",
                "On coil-split pickups, verify the tap wire isn't accidentally grounded",
            ],
            "outside_kiss_scope": True,
        },
    }

    for key, info in diagnoses.items():
        if key in symptom_lower or symptom_lower in key:
            return {"symptom": symptom, **info}

    return {
        "symptom": symptom,
        "likely_causes": ["Electrical symptom not recognized in standard diagnostic list."],
        "diagnostic_questions": [
            "Can you describe the electrical issue in more detail?",
            "When does it happen — at rest, when playing, when moving the cable?",
            "Does it affect all pickup positions?",
        ],
        "recommended_fixes": ["Describe the issue in more detail for a targeted diagnosis."],
        "outside_kiss_scope": True,
        "additional_notes": f"'{symptom}' wasn't matched. Please describe the electrical behavior you're experiencing.",
    }


def get_string_recommendations(
    tuning: str, scale_length: str = None, playing_style: str = None
) -> dict:
    """Returns string gauge recommendations based on tuning, scale length, and playing style.

    Args:
        tuning: Target tuning. Examples: standard-e, eb, drop-d, drop-c, d-standard,
            c-standard, open-g, open-e, dadgad.
        scale_length: Guitar scale length in inches. Common values: 24.75 (Gibson),
            25 (PRS), 25.5 (Fender), 26.5 (baritone), or a custom value.
        playing_style: Player's style. Examples: light-picking, heavy-picking, aggressive,
            fingerstyle, hybrid-picking, heavy-rhythm, lead.
    """
    tuning_lower = tuning.lower().replace(" ", "-").replace("_", "-")

    tuning_data = {
        "standard-e": {
            "label": "Standard E (E A D G B e)",
            "base_gauges": {
                "light": "9-42",
                "medium": "10-46",
                "heavy": "11-49",
            },
            "notes": "The most flexible tuning for gauge choice. Most players use 9s or 10s.",
        },
        "eb": {
            "label": "Eb Standard (Eb Ab Db Gb Bb eb) — half step down",
            "base_gauges": {
                "light": "9-42 or 10-46",
                "medium": "10-46 or 11-49",
                "heavy": "11-49 or 11-52",
            },
            "notes": "Drop half a step means slightly less tension — many players bump up one gauge size to compensate.",
        },
        "drop-d": {
            "label": "Drop D (D A D G B e)",
            "base_gauges": {
                "light": "9-42 or 10-46",
                "medium": "10-46",
                "heavy": "10-52 or 11-52",
            },
            "notes": "Only the low E drops — tension loss is minimal. Standard gauge works fine. A .052\" or .054\" low E adds tension for heavier playing.",
        },
        "drop-c": {
            "label": "Drop C (C G C F A D)",
            "base_gauges": {
                "light": "10-52",
                "medium": "11-54",
                "heavy": "12-56",
            },
            "notes": "Significant tension drop — heavier gauges required. On a 25.5\" scale, 11-52 or 11-54 is the standard recommendation. Lighter gauge will feel floppy.",
        },
        "d-standard": {
            "label": "D Standard (D G C F A D) — full step down",
            "base_gauges": {
                "light": "10-46 or 10-52",
                "medium": "11-49 or 11-52",
                "heavy": "12-56",
            },
            "notes": "Full step down requires at least 10s on a standard scale to avoid floppiness. 11s are more common for rhythm players.",
        },
        "c-standard": {
            "label": "C Standard (C F Bb Eb G C) — two steps down",
            "base_gauges": {
                "light": "11-54",
                "medium": "12-56",
                "heavy": "13-56",
            },
            "notes": "Heavy gauges required — strings get very slack at this tuning on standard scale lengths. Consider a baritone or extended scale guitar for regular C standard use.",
        },
        "open-g": {
            "label": "Open G (D G D G B D)",
            "base_gauges": {
                "light": "10-46",
                "medium": "11-49",
                "heavy": "11-52",
            },
            "notes": "Mixed tension — some strings go up, some go down. 10s or 11s work well. Keith Richards famously removes the low E string and uses 5 strings.",
        },
        "open-e": {
            "label": "Open E (E B E G# B E)",
            "base_gauges": {
                "light": "10-46",
                "medium": "10-46 or 11-49",
                "heavy": "11-49",
            },
            "notes": "Several strings tuned UP from standard — use lighter gauges to avoid excessive tension. Slide players often prefer lighter strings for easier action.",
        },
        "dadgad": {
            "label": "DADGAD (D A D G A D)",
            "base_gauges": {
                "light": "10-46",
                "medium": "11-49",
                "heavy": "12-54",
            },
            "notes": "Celtic and fingerstyle favorite. Gauges depend heavily on playing style — fingerpickers often prefer 12s or 13s for tone, lead players use 10s or 11s.",
        },
    }

    matched_tuning = None
    for key, data in tuning_data.items():
        if key in tuning_lower or tuning_lower in key:
            matched_tuning = data
            break

    if not matched_tuning:
        matched_tuning = {
            "label": f"Custom/unrecognized tuning: {tuning}",
            "base_gauges": {
                "light": "10-46",
                "medium": "11-49",
                "heavy": "12-56",
            },
            "notes": "Tuning not in standard list — recommendations based on general principles. Describe the tuning in detail for a more specific recommendation.",
        }

    style_modifier = ""
    if playing_style:
        style_lower = playing_style.lower()
        if any(s in style_lower for s in ["light", "fingerstyle", "fingerpick"]):
            style_modifier = "Lean toward the lighter end of the recommended range — lighter strings are easier to fret and bend cleanly."
        elif any(s in style_lower for s in ["heavy", "aggressive", "rhythm", "djent", "metal"]):
            style_modifier = "Lean toward the heavier end of the recommended range — heavier strings hold tension better under aggressive playing and stay in tune more consistently."
        elif any(s in style_lower for s in ["lead", "bend", "solo"]):
            style_modifier = "Lead players who bend frequently often prefer lighter gauges within the range for easier string bending. Balance against the tuning tension requirement."
        elif any(s in style_lower for s in ["hybrid", "mixed"]):
            style_modifier = "Hybrid pickers often prefer medium gauges — enough tension for clarity, light enough for comfortable string articulation."

    scale_modifier = ""
    if scale_length:
        try:
            scale = float(scale_length.replace('"', "").strip())
            if scale <= 24.75:
                scale_modifier = f"Shorter scale ({scale_length}\" — Gibson range): Strings will feel slightly lighter/floppier at this scale. Consider going one gauge heavier than you might on a 25.5\" scale to maintain comparable feel and tension."
            elif scale >= 26.5:
                scale_modifier = f"Extended/baritone scale ({scale_length}\"): This longer scale increases string tension significantly. You may be able to use lighter gauges than listed while maintaining good feel, or use standard gauges for very high tension."
            elif 25.0 <= scale <= 25.5:
                scale_modifier = f"Standard scale ({scale_length}\" — Fender/PRS range): The recommendations above are calibrated for this scale length."
        except ValueError:
            scale_modifier = f"Scale length '{scale_length}' wasn't parsed as a number — please provide it in inches (e.g., 25.5)."

    return {
        "tuning": matched_tuning["label"],
        "recommended_gauges": matched_tuning["base_gauges"],
        "tuning_notes": matched_tuning["notes"],
        "scale_modifier": scale_modifier if scale_modifier else None,
        "style_modifier": style_modifier if style_modifier else None,
        "brand_suggestions": [
            "Ernie Ball (Slinky series) — widely available, consistent quality",
            "D'Addario (NYXL or EXL series) — excellent intonation, long lasting",
            "Elixir (Nanoweb or Polyweb) — coated, much longer string life, preferred by many gigging players",
            "GHS Boomers — bright tone, popular with rock players",
        ],
    }


get_setup_flow_tool = FunctionTool(get_setup_flow)
diagnose_issue_tool = FunctionTool(diagnose_issue)
diagnose_electrical_issue_tool = FunctionTool(diagnose_electrical_issue)
get_string_recommendations_tool = FunctionTool(get_string_recommendations)
