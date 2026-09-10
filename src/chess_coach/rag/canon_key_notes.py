from typing import Any

def _note(
    principle: str,
    phase: str,
    summary: str,
    themes: list[str],
    specificity: int = 3,
    features: list[str] | None = None,
    san_lines: list[str] | None = None,
    openings: list[str] | None = None,
    games: list[str] | None = None,
    slots: dict[str, str] | None = None,
    conditions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "principle": principle,
        "phase": phase,
        "summary": summary,
        "specificity": int(specificity),
        "themes": themes,
        "features": features or [],
        "san_lines": san_lines or [],
        "fens": [],
        "openings": openings or [],
        "games": games or [],
    }
    if slots:
        row["slots"] = {
            k: str(v).strip()
            for k, v in slots.items()
            if str(v).strip() and k in ("worked", "attention", "lesson", "plan")
        }
    if conditions:
        row["conditions"] = list(conditions)
    return row


CANON_KEY_NOTES: dict[str, list[dict]] = {
    "attack.f7_f2_vulnerability": [
        _note("Early king-pawn weakness", "opening", "Before launching an attack, check whether f7 or f2 is defended only by the king. Rapid development and control of central routes can turn that early weakness into a forcing target.", ["king attack", "development", "forcing play"], 1, ["unmoved-king", "hanging-f7", "hanging-f2", "open-diagonal"]),
        _note("Attacker coordination", "opening", "Pressure on f7 or f2 becomes dangerous when a bishop attacks along the diagonal and a queen or knight can join with tempo. Calculate checks first, but do not sacrifice unless the remaining attackers can reach the king.", ["piece coordination", "checks", "sacrifice"], 3, ["bishop-on-c4", "bishop-on-c5", "queen-near-kingside", "knight-jump"]),
        _note("F-file king skewer", "any", "When a check drives the king onto the f-file, look for a second check that captures on f7 or f2 and exposes a queen, rook, or loose piece behind the king. The first check is valuable because it creates the alignment for a skewer.", ["skewer", "checks", "material gain"], 5, ["king-on-f-file", "hanging-f7", "hanging-f2", "aligned-heavy-piece"]),
        _note("Threat as leverage", "opening", "A threat against f7 or f2 can be useful even when it does not win immediately. Forcing the defender into passive protection may delay castling, disconnect the pieces, or let you seize the center.", ["initiative", "king safety", "central control"], 2, ["uncastled-king", "overloaded-defender", "development-lead"]),
    ],
    "attack.greek_gift": [
        _note("Greek Gift pattern", "middlegame", "The Greek Gift is a bishop sacrifice on h7 or h2 designed to drag the castled king out and bring the queen and knight into a mating attack. Its soundness depends on access routes, not on the sacrifice alone.", ["bishop sacrifice", "king attack", "mating net"], 2, ["castled-kingside", "hanging-h7", "hanging-h2", "queen-knight-coordination"]),
        _note("Entry-square checklist", "middlegame", "Before sacrificing on h7, verify that the knight can reach g5 with tempo, the queen can enter on h5 or the h-file, and the defending king cannot escape comfortably through g6, f6, or g8.", ["calculation", "checks", "escape squares"], 4, ["bishop-on-d3", "knight-near-g5", "queen-access-h5", "castled-kingside"]),
        _note("Defender and center test", "middlegame", "The sacrifice is stronger when the defender on f6 is absent, pinned, or unable to control h7 and g4, while the attacking side has a stable center. If the center can be opened against your own king, the combination may be too slow.", ["removing the defender", "central stability", "king safety"], 3, ["missing-f6-knight", "pinned-f6-knight", "closed-center", "bishop-on-c1-h6-diagonal"]),
        _note("Forcing continuation", "middlegame", "After the king accepts the Greek Gift, calculate forcing moves in order: knight checks, queen checks, and captures that remove flight squares. A quiet move is justified only if it creates an unavoidable threat and the king has no simplifying defense.", ["checks", "captures", "mating attack"], 5, ["king-on-h7", "king-on-h2", "knight-on-g5", "queen-on-h-file"]),
    ],
    "attack.initiative": [
        _note("Threat with development", "any", "The initiative belongs to the side making threats that demand answers. Preserve it by choosing moves that improve a piece while creating a check, capture, or concrete threat.", ["initiative", "tempo", "forcing play"], 1, ["active-pieces", "tempo-gain", "opponent-on-defense"]),
        _note("Queenless initiative", "endgame", "An initiative can survive a queen trade when active rooks, advanced pawns, or exposed pieces continue to force defensive moves. Do not assume simplification ends the attack; reassess king activity and tactical threats.", ["piece activity", "simplification", "tempo"], 3, ["queens-off", "active-rook", "advanced-passed-pawn", "exposed-piece"]),
        _note("Attack as defense", "middlegame", "When both kings are vulnerable, the player who attacks first often becomes safer because the opponent's pieces are tied to defense. Favor forcing moves that deny the enemy time to organize counterplay.", ["king safety", "counterplay", "forcing play"], 2, ["both-kings-exposed", "uncoordinated-defense", "active-queen"]),
        _note("Pawn-driven tempo net", "endgame", "An advanced pawn can maintain the initiative by attacking a rook's squares while a knight threatens a fork or mating net. Calculate the pawn push before routine king centralization, especially when every rook retreat loses coordination.", ["advanced pawn", "fork", "piece restriction"], 5, ["advanced-passed-pawn", "restricted-rook", "knight-fork", "active-king"]),
    ],
    "attack.king_safety": [
        _note(
            "Relative king safety",
            "any",
            "- Compare open lines, defenders, and flight squares before committing to an attack.\n- Castle or close files before the centre opens if your king is still exposed.",
            ["attack.king_safety", "piece.coordination"],
            1,
            ["open-file-near-king", "weak-color-complex", "limited-flight-squares", "uncastled-king"],
            slots={
                "worked": "your king stayed safer than the opposing one behind a useful shield",
                "attention": "open lines and thin defenders still expose the king",
                "lesson": "compare open lines, defenders, and flight squares before committing material",
                "plan": "castle or close the dangerous files before opening the centre",
            },
            conditions=[
                {"softKey": "attack.king_safety", "polarity": "any"},
                {"metric": "king_attackers_pct", "polarity": "bad"},
                {"metric": "opp_king_uncastled", "polarity": "good"},
                {"feature": "uncastled-king", "polarity": "bad"},
            ],
        ),
        _note(
            "Open the attacking wing",
            "middlegame",
            "- Storm with the pawn beside the chain head so heavy pieces gain open files.\n- Do not push if the defender can seal the wing and counterattack the abandoned pawns.",
            ["attack.king_safety", "attack.opposite_side_castling", "imbalance.space"],
            3,
            ["castled-kingside", "locked-pawn-chain", "adjacent-pawn-break", "rook-behind-pawn"],
            slots={
                "worked": "the pawn storm began opening useful attacking files",
                "attention": "the wing advance still needs entry squares before it creates only weaknesses",
                "lesson": "push the pawn beside the chain head to open files without stranding your own king",
                "plan": "bring heavy pieces behind the storm once a file opens",
            },
            conditions=[
                {"softKey": "attack.king_safety", "polarity": "good"},
                {"softKey": "attack.opposite_side_castling", "polarity": "any"},
                {"situation": "pawn_storm", "polarity": "any"},
                {"feature": "castled-kingside", "polarity": "any"},
            ],
        ),
        _note(
            "Remove the key defender",
            "middlegame",
            "- Identify the key defender of the castled king before calculating sacrifices.\n- Pin, exchange, or deflect that piece so checks become forcing.",
            ["attack.king_safety", "motif.pin_and_skewer", "attack.initiative"],
            2,
            ["castled-king", "overloaded-defender", "queen-rook-battery"],
            slots={
                "worked": "pressure already fixed a key defender near the king",
                "attention": "the key defender still holds the position together",
                "lesson": "remove or overload the key defender before the sacrifice lands",
                "plan": "pin or exchange the defender, then force with checks",
            },
            conditions=[
                {"softKey": "attack.king_safety", "polarity": "bad"},
                {"feature": "overloaded-defender", "polarity": "any"},
            ],
        ),
        _note(
            "Pawn-storm commitment",
            "middlegame",
            "- A kingside pawn advance only compensates when it creates entry squares now.\n- If the wing can be closed, stop and fix the abandoned queenside instead.",
            ["attack.king_safety", "imbalance.space"],
            4,
            ["advanced-g-pawn", "queenside-weakness", "closed-kingside", "open-g-file"],
            slots={
                "worked": "the kingside advance created real entry pressure",
                "attention": "the storm risks leaving queenside holes without entry squares",
                "lesson": "commit to the storm only when entry squares appear immediately",
            },
            conditions=[
                {"softKey": "attack.king_safety", "polarity": "bad"},
                {"feature": "queenside-weakness", "polarity": "bad"},
            ],
        ),
    ],
    "attack.opposite_side_castling": [
        _note("Race of attacks", "middlegame", "With opposite-side castling, speed usually matters more than pawn weaknesses because each side can advance pawns toward the enemy king. Count tempi and compare which attack opens lines first.", ["opposite-side castling", "pawn storm", "tempo"], 1, ["opposite-side-castling", "pawn-storm", "unclear-center"]),
        _note("Sicilian wing race", "middlegame", "In many Sicilian Defense structures with opposite-side castling, White attacks with kingside pawns while Black expands with queenside pawns. Each pawn push should either open a file, dislodge a defender, or gain a tempo on a piece.", ["Sicilian Defense", "pawn storm", "wing attack"], 3, ["opposite-side-castling", "scheveningen-structure", "kingside-pawn-storm", "queenside-pawn-majority"], openings=["Sicilian Defense", "Najdorf Variation", "Scheveningen Variation"]),
        _note("Dislodge the c3 knight", "middlegame", "A queenside pawn thrust that drives a knight from c3 can gain a crucial attacking tempo and reduce control of d5. Time it before the knight occupies d5 or the opened files become more useful to the castled king's defender.", ["tempo", "piece displacement", "queenside attack"], 5, ["knight-on-c3", "b-pawn-advance", "weak-d5", "queenside-castled-king"], openings=["Sicilian Defense"]),
        _note("Center before wing", "middlegame", "Do not attack on autopilot when the center can open. A central break with check or tempo may be faster than either wing attack, and an exposed king can make further pawn advances impossible.", ["central break", "king safety", "counterplay"], 2, ["opposite-side-castling", "unresolved-center", "central-pawn-break"]),
    ],
    "endgame.strategic.active_king": [
        _note(
            "Activate the king when tactical danger has subsided.",
            "endgame",
            "- Centralize the king to attack pawns, support passers, and deny entry squares.\n- Do not rush pawn pushes while the king still sits on the back rank.",
            ["endgame.strategic.active_king", "piece.simplification"],
            1,
            ["reduced-material", "king-entry-squares", "weak-pawns"],
            slots={
                "worked": "the ending simplified enough for the king to become a fighting piece",
                "attention": "the king is still too passive to escort pawns or seize key squares",
                "lesson": "centralize the king once tactical danger has subsided",
                "plan": "bring the king forward before further pawn advances",
            },
            conditions=[
                {"softKey": "endgame.strategic.active_king", "polarity": "any"},
                {"metric": "king_centralization", "polarity": "bad"},
                {"metric": "vector_king_mechanics", "polarity": "bad"},
            ],
        ),
        _note(
            "Convert king activity into restriction before changing the pawn structure.",
            "endgame",
            "- Secure a central outpost and restrict the enemy king first.\n- Only then create or advance a passed pawn.",
            ["endgame.strategic.active_king", "structure.passed_pawn"],
            3,
            ["central-king-outpost", "opposition", "pawn-majority"],
            slots={
                "worked": "your king already claimed useful central ground",
                "attention": "the pawn structure still needs changing only after the enemy king is restricted",
                "lesson": "convert king activity into restriction before changing the pawn structure",
                "plan": "fix a passer only after the opposing king is cut off",
            },
            conditions=[
                {"softKey": "endgame.strategic.active_king", "polarity": "good"},
                {"metric": "conversion_state", "polarity": "good"},
            ],
        ),
        _note(
            "Use a pawn move to create a protected route for the king.",
            "endgame",
            "- Prefer a tempo-gaining pawn move that opens the king's route.\n- Avoid pawn rushes that expose new weaknesses before entry.",
            ["endgame.strategic.active_king", "structure.passed_pawn"],
            4,
            ["king-route", "tempo-gaining-pawn-move", "central-entry"],
            slots={
                "worked": "a pawn lever already opened a path for the king",
                "attention": "the king still needs a protected route before the next pawn push",
                "lesson": "use a forcing pawn move to create a safe king entry route",
            },
            conditions=[
                {"softKey": "endgame.strategic.active_king", "polarity": "bad"},
                {"feature": "tempo-gaining-pawn-move", "polarity": "any"},
            ],
        ),
    ],
    "endgame.strategic.pawn_break": [
        _note("Judge a pawn break by the position it creates, not by the pawn it trades.", "endgame", "Do not treat every endgame pawn move as a race toward promotion. A pawn break is strongest when it opens an entry file, creates a passed pawn, or forces a lasting weakness.", ["pawn break", "passed pawn", "endgame strategy"], 1, ["pawn lever", "entry file", "structural weakness"]),
        _note("Attack a pawn hook to transform a fixed structure.", "endgame", "Look for an advanced enemy pawn that acts as a hook. Challenging it can force an unfavorable capture, open a file for the rook, or leave a neighboring pawn isolated.", ["pawn break", "pawn hook", "rook activity"], 3, ["advanced enemy pawn", "forced recapture", "open file"]),
        _note("Use the break to overload the defending rook.", "endgame", "Before playing a break such as f5-f4 in a rook ending, check whether it drives the defending rook away from a pawn or rank. The break is valuable when the rook cannot maintain both active play and protection.", ["rook ending", "pawn break", "overloading"], 4, ["f-pawn break", "rook displacement", "loose pawn"]),
    ],
    "endgame.theoretical.fortress": [
        _note("Test the defender's setup for zugzwang or a second weakness before assuming it can be broken.", "endgame", "A material advantage does not guarantee a win when the defender can build a fortress. Before simplifying, identify whether the defending king and pieces can hold fixed squares without being forced to concede.", ["fortress", "defensive technique", "simplification"], 1, ["closed entry squares", "stable blockade", "no pawn breaks"]),
        _note("Stretch an opposite-bishop fortress across two fronts.", "endgame", "Opposite-colored bishop endings often become fortresses because the defender can control the promotion color while the attacking bishop cannot challenge it. Keep pawns on squares the defending bishop must guard and seek threats on both wings.", ["fortress", "opposite bishops", "two weaknesses"], 3, ["opposite-colored bishops", "split pawn wings", "blockade squares"]),
        _note("Recognize the wrong-bishop rook-pawn fortress before trading into it.", "endgame", "Against a bishop-and-rook-pawn fortress, first verify whether the bishop controls the pawn's promotion square. If the defending king can reach the corner that the bishop cannot drive it from, the extra pawn may be useless.", ["fortress", "wrong bishop", "rook pawn"], 5, ["rook pawn", "wrong-colored bishop", "king in promotion corner"]),
    ],
    "endgame.theoretical.lucena": [
        _note("Use the rook as shelter for the advancing king.", "endgame", "In winning rook endings, place the rook where it can shield the king from checks while the king escorts the passed pawn. Coordination matters more than checking at random.", ["rook ending", "passed pawn", "king shelter"], 2, ["advanced passed pawn", "checking distance", "rook coordination"]),
        _note("Create room for the rook to interpose against side checks.", "endgame", "The Lucena method applies when the stronger king stands in front of a pawn on the seventh rank and the enemy king is cut off. Move the rook away, force side checks, and prepare to build a bridge.", ["Lucena", "rook ending", "bridge building"], 4, ["pawn on seventh rank", "king in front of pawn", "cut-off king"]),
        _note("Build the fourth-rank bridge to stop lateral checks.", "endgame", "In the Lucena position, build the bridge by placing the rook on the fourth rank, stepping the king out under checks, and interposing the rook when the defender checks from the side. This ends the checking mechanism and permits promotion.", ["Lucena", "bridge building", "theoretical rook ending"], 5, ["rook on fourth rank", "side checks", "interposition"]),
    ],
    "endgame.theoretical.philidor": [
        _note("Restrict the king before beginning rear checks.", "endgame", "The defender in a rook ending should keep the attacking king away from the promotion zone and preserve checking distance. Passive defense becomes dangerous once the stronger king gains shelter.", ["rook ending", "defensive technique", "checking distance"], 2, ["rook versus rook and pawn", "king restriction", "rear checks"]),
        _note("Use third-rank restriction, then switch to rear checks.", "endgame", "The Philidor defense holds when the pawn has not passed the fifth rank: keep the rook on the third rank to bar the enemy king. When the pawn advances, retreat the rook and check from behind.", ["Philidor", "rook ending", "third-rank defense"], 4, ["pawn on fifth rank or lower", "rook on third rank", "rear checks"]),
        _note("Time the rook's retreat only after the pawn blocks its own king.", "endgame", "In the central-pawn Philidor setup, do not abandon the third rank while the attacking king is still blocked. After the pawn advances to the sixth rank, move the rook far enough away to deliver repeated checks from the rear.", ["Philidor", "theoretical rook ending", "rear checks"], 5, ["central pawn on sixth rank", "blocked attacking king", "long checking distance"]),
    ],
    "endgame.theoretical.triangulation": [
        _note("Lose a tempo without changing the essential position.", "endgame", "Triangulation is a controlled loss of tempo: the king uses three moves to return to the same square while forcing the opponent to move. Use it only after identifying the desired zugzwang.", ["triangulation", "zugzwang", "king maneuver"], 2, ["three-square king route", "move-order battle", "fixed pawns"]),
        _note("Treat spare pawn moves as tempi, not automatic improvements.", "endgame", "Count reserve pawn tempi before triangulating. A harmless pawn move may decide who must yield the opposition, but pushing too soon can remove a square your own king needs.", ["triangulation", "reserve tempi", "opposition"], 3, ["unmoved pawn", "opposition", "king entry square"]),
        _note("Preserve the king's triangulation squares when fixing the pawn structure.", "endgame", "In king-and-pawn endings, triangulate only when the returning king move hands the opponent the same position with the move. Confirm that the pawn has enough reserve tempi and does not occupy a key square such as e4 that the king needs for the maneuver.", ["triangulation", "key squares", "pawn ending"], 5, ["king and pawn ending", "e4 key square", "exact tempo count"]),
    ],
    "endgame.theoretical.vancura": [
        _note("Attack the rook pawn laterally instead of waiting passively behind it.", "endgame", "A rook can often draw against a rook pawn by attacking it from the side while the king remains near the opposite wing. Side activity prevents the stronger king from finding shelter.", ["rook ending", "side checks", "defensive activity"], 2, ["rook pawn", "lateral rook activity", "exposed king"]),
        _note("Combine lateral pawn attacks with flank checks.", "endgame", "The Vancura defense works against a rook pawn on the sixth rank when the stronger rook protects it from behind. Keep the defending rook active from the side and check as soon as the king approaches the pawn.", ["Vancura", "rook ending", "rook pawn"], 4, ["rook pawn on sixth rank", "attacking rook behind pawn", "side checks"]),
        _note("Maintain side distance and preserve the switch to rear checks.", "endgame", "In the Vancura position, place the rook far enough along the fourth rank to attack the pawn laterally without being chased by the king. Keep the defending king away from mating nets and switch to rear checks if the pawn advances.", ["Vancura", "theoretical rook ending", "lateral defense"], 5, ["defending rook on fourth rank", "rook pawn on sixth rank", "checking transition"]),
    ],
    "imbalance.bishop_pair": [
        _note("Evaluate the bishop pair by its access to open diagonals.", "middlegame", "The bishop pair matters most in open positions with targets on both colors. Preserve both bishops when pawn breaks can open lines, but do not value the pair more than king safety, development, or pawn structure.", ["bishop pair", "open position", "king safety"], 1, ["two bishops", "open diagonals", "targets on both wings"]),
        _note("Open the position and create targets on both color complexes.", "middlegame", "With the bishop pair, use pawn breaks to remove central blockades and create play on both wings. Avoid fixing all pawns on one color, because that can leave one bishop without useful work.", ["bishop pair", "pawn break", "color complexes"], 3, ["central tension", "play on both wings", "mobile pawns"], openings=["Carlsbad structure"]),
        _note("Use the outside majority to make the knight defend two distant fronts.", "endgame", "In an endgame with bishops against a knight and bishop, an outside pawn majority increases the power of the bishop pair. Stretch the knight with threats on both wings, improve the king, and only then create the outside passer.", ["bishop pair", "outside majority", "two weaknesses"], 4, ["bishop pair versus bishop and knight", "outside pawn majority", "active king"]),
    ],
    "imbalance.good_vs_bad_bishop": [
        _note("Judge a bishop by the structure and its available duties.", "middlegame", "A bishop is bad when its own fixed pawns block its diagonals or create targets on its color. Improve it by changing the pawn structure, moving it outside the chain, or exchanging it for an active enemy piece.", ["good bishop", "bad bishop", "pawn structure"], 1, ["fixed pawn chain", "restricted bishop", "color-complex weaknesses"]),
        _note("Fix targets on the bad bishop's color and simplify around them.", "endgame", "Against a bad bishop, fix enemy pawns on that bishop's color and occupy the opposite color with your king or knight. Trade active enemy pieces so the bishop's structural burden becomes decisive.", ["good vs bad bishop", "restriction", "simplification"], 3, ["pawns fixed on bishop color", "strong knight", "minor-piece exchange"]),
        _note("Break the pawn chain before the bad bishop becomes the only minor piece.", "middlegame", "In a French-style locked center, a bishop trapped behind the pawn chain can remain strategically inferior to a knight on d4 or e5. The restricted side should challenge the chain with ...f6 or free the bishop before exchanging other active pieces.", ["bad bishop", "French structure", "pawn break"], 4, ["locked center", "bishop behind pawn chain", "knight outpost"], openings=["French Defense"]),
    ],
    "imbalance.knight_vs_bishop": [
        _note("Match the minor piece to the future pawn structure.", "middlegame", "Knights thrive in closed positions with stable outposts; bishops thrive in open positions and across both wings. Before choosing an exchange, predict whether the pawn structure will remain fixed or open.", ["knight vs bishop", "pawn structure", "piece activity"], 1, ["closed or open center", "outpost", "long diagonal"]),
        _note("The bishop stretches; the knight blockades.", "endgame", "A bishop usually gains value when play occurs on both wings or an outside passed pawn appears. The knight should seek a blockade, avoid being stretched by distant threats, and keep enough pawns to anchor central outposts.", ["knight vs bishop", "outside passer", "blockade"], 3, ["play on both wings", "outside pawn majority", "central outpost"]),
        _note("Use the king and outside majority to overload a short-range knight.", "endgame", "In a bishop-versus-knight ending with an outside majority and the more active king, open a second wing before creating the passer. The knight cannot switch fronts quickly, so force it into a passive holding pattern and improve the bishop's diagonal.", ["bishop vs knight", "outside majority", "active king"], 4, ["single bishop versus single knight", "outside majority", "two-wing play"]),
    ],
    "imbalance.material_asymmetry": [
        _note("Translate material differences into concrete jobs and plans.", "middlegame", "Unequal material must be evaluated by function, not points alone. Compare king safety, piece activity, pawn structure, and the number of targets each side can attack.", ["material asymmetry", "piece activity", "king safety"], 1, ["unequal material", "dynamic compensation", "structural targets"]),
        _note("The material side reduces activity; the compensating side preserves it.", "middlegame", "When you have the material advantage, exchange the opponent's most active pieces and preserve the pawns that can become passers. When you have compensation, avoid passive trades and create immediate threats against the king or weak pawns.", ["material advantage", "compensation", "simplification"], 2, ["extra material", "active enemy pieces", "passed-pawn potential"]),
        _note("Demand durable square control before accepting long-term material deficit.", "middlegame", "An exchange sacrifice is justified when the minor piece gains a stable blockade, key-square control, and durable targets that the rook cannot attack. If control of a square such as e5 disappears after one pawn break, the compensation is temporary rather than positional.", ["exchange sacrifice", "restriction", "blockade"], 4, ["rook versus minor piece", "e5 outpost", "stable pawn structure"], openings=["King's Indian structures", "Catalan"]),
    ],
    "imbalance.space": [
        _note(
            "Use space to improve pieces, not merely to claim territory.",
            "middlegame",
            "- Use extra room to improve pieces and restrict the opponent.\n- Support the base of the advanced chain so space does not become a target.",
            ["imbalance.space", "positional.restriction", "piece.coordination"],
            1,
            ["advanced-pawn-chain", "restricted-enemy-pieces", "pawn-chain-base"],
            slots={
                "worked": "you claimed useful space that restricts their pieces",
                "attention": "the space edge still needs piece support at the chain base",
                "lesson": "use space to improve pieces, not merely to claim empty territory",
                "plan": "reinforce the base, then improve the worst-placed piece",
            },
            conditions=[
                {"softKey": "imbalance.space", "polarity": "any"},
                {"metric": "space_advantage_pct", "polarity": "any"},
            ],
        ),
        _note(
            "Convert space by restricting counterplay before opening lines.",
            "middlegame",
            "- Prevent the freeing break before releasing central tension.\n- Prepare the lever on the side your chain points toward.",
            ["imbalance.space", "positional.pawn_break", "methodology.prophylactic_thinking"],
            3,
            ["central-tension", "freeing-break", "wing-pawn-lever"],
            slots={
                "worked": "space already limits their freeing ideas",
                "attention": "their freeing break still needs restraining before you open lines",
                "lesson": "convert space by stopping counterplay before releasing the centre",
                "plan": "prepare the wing lever only after the freeing break is under control",
            },
            conditions=[
                {"softKey": "imbalance.space", "polarity": "good"},
                {"softKey": "positional.pawn_break", "polarity": "bad"},
            ],
        ),
        _note(
            "Break beside the head of the pawn chain only after completing development.",
            "middlegame",
            "- Support the lever with pieces before expanding beside the chain head.\n- Pushing without control trades space for their activity.",
            ["imbalance.space", "positional.pawn_break"],
            4,
            ["pawn-on-d5", "c-pawn-lever", "queenside-expansion"],
            slots={
                "worked": "development is ready to support a space-gaining lever",
                "attention": "the lever beside the chain head still lacks piece support",
                "lesson": "break beside the chain head only after pieces cover the resulting files",
            },
            conditions=[
                {"softKey": "imbalance.space", "polarity": "bad"},
                {"feature": "c-pawn-lever", "polarity": "any"},
            ],
        ),
    ],
    "methodology.candidate_moves": [
        _note("Build candidates before calculating", "all", "Before calculating, list a small set of moves that answer the position's most urgent need: checks, captures, threats, defensive resources, and improving moves.", ["candidate moves", "calculation"], 1, []),
        _note("Balance forcing and quiet candidates", "middlegame", "Compare forcing moves with quiet alternatives. A move that creates immediate pressure can outrank a slow improvement, but only after checking the opponent's strongest reply.", ["candidate moves", "decision making"], 3, ["initiative", "opponent threats"], games=["Baryshpolets vs Turov 2012"]),
        _note("Generate candidates by function", "endgame", "When one pawn is attacked and another can be captured, include defending, counterattacking, and changing the pawn structure as separate candidates. Calculate each through the opponent's most forcing response before comparing outcomes.", ["candidate moves", "endgame technique", "calculation"], 5, ["attacked pawn", "counterattack", "pawn structure"], games=["Alexander Alekhine vs Jose Raul Capablanca 1927"]),
    ],
    "methodology.comparison_and_elimination": [
        _note("Compare outcomes, not appearances", "all", "Do not choose the first acceptable move. Compare candidates by the resulting position, then eliminate those that fail tactically or worsen the key imbalance.", ["comparison", "decision making"], 1, []),
        _note("Adjust analogies for concrete differences", "middlegame", "Use a familiar pawn structure as a reference, but identify what changed: piece placement, available breaks, king safety, and tempi can reverse the usual plan.", ["comparison", "pawn structures", "strategic planning"], 3, ["piece placement", "pawn breaks", "king safety"], openings=["Sicilian Defense"]),
        _note("Eliminate by counterplay and coordination", "middlegame", "When comparing an attack with a positional regrouping, ask whether the pawn storm is still risk-free, whether the blockader can attack as well as restrain, and which candidate leaves the opponent least counterplay.", ["comparison", "blockade", "piece coordination"], 5, ["pawn storm", "blockader", "counterplay"], openings=["King's Indian Defense"], games=["Radoslaw Wojtaszek vs Alexei Fedorov 2012"]),
    ],
    "methodology.prophylactic_thinking": [
        _note("Identify the opponent's next idea", "all", "Before every serious decision, ask what the opponent wants next and which of their pieces or pawn breaks will make that plan work.", ["prophylaxis", "thinking process"], 1, []),
        _note("Combine prevention with improvement", "middlegame", "Prefer a useful move that both improves your position and hinders the opponent. Pure defense is less attractive when development, coordination, or a pawn lever can be restricted simultaneously.", ["prophylaxis", "piece coordination"], 3, ["development", "pawn lever"], games=["Mark Taimanov vs Miguel Najdorf 1953"]),
        _note("Deny the key regrouping square", "middlegame", "If the opponent needs a queen retreat or regrouping square to free cramped pieces, control that square first. Then improve calmly while their pieces remain locked behind their pawn structure.", ["prophylaxis", "restriction", "piece maneuvering"], 5, ["regrouping square", "cramped pieces", "pawn structure"], openings=["Ruy Lopez"], games=["Baryshpolets vs Turov 2012"]),
    ],
    "methodology.visualization": [
        _note("Calculate toward a complete final position", "all", "Visualize the final position, not merely the move sequence. Track every piece, changed line, newly attacked square, and removed defender.", ["visualization", "calculation"], 1, []),
        _note("Strengthen coordinate and piece memory", "all", "Train board vision by naming square colors and coordinates, then reconstructing piece placement from memory. Accurate calculation depends on preserving the board after each imagined move.", ["visualization", "working memory"], 3, ["square colors", "piece placement"]),
        _note("Visualize structural transformations", "middlegame", "In a closed center, visualize candidate pawn breaks through the resulting files and diagonals. Confirm where each minor piece will operate after exchanges before deciding whether a space-gaining break helps.", ["visualization", "pawn structure", "minor piece battles"], 5, ["closed center", "pawn breaks", "files", "diagonals"], openings=["King's Indian Defense"], games=["Radoslaw Wojtaszek vs Alexei Fedorov 2012"]),
    ],
    "motif.discovered_attack": [
        _note("Unmask the line piece", "any", "A discovered attack occurs when one piece moves away and uncovers an attack by a piece behind it. Search for moving pieces that can leave a rook, bishop, or queen aimed at a valuable target.", ["discovered attack", "line piece", "tempo"], 1, ["aligned-pieces", "blocked-line", "loose-target"]),
        _note("Double threat discovery", "any", "The strongest discoveries make the moving piece create a second threat, especially check. The opponent must answer the new threat while the uncovered rook, bishop, or queen attacks material behind it.", ["double attack", "discovered check", "forcing play"], 3, ["line-piece-battery", "moving-blocker", "exposed-king"]),
        _note("Checking discovery", "any", "When a queen and king or queen and rook lie on the same line, look for a check by the blocking piece that reveals an attack on the rear target. Answering the check may leave the valuable piece undefended.", ["discovered check", "queen attack", "material gain"], 4, ["aligned-queen", "line-piece-battery", "checking-blocker"]),
        _note("Sacrificial discovery", "middlegame", "A bishop sacrifice on h2 or h7 can function as a discovery when accepting it opens a queen or rook attack on a distant loose piece. Calculate both the king attack and the newly opened line before deciding whether the sacrifice is sound.", ["bishop sacrifice", "discovered attack", "deflection"], 5, ["bishop-on-d6", "bishop-on-d3", "hanging-h2", "hanging-h7", "loose-piece-on-open-line"]),
    ],
    "motif.intermediate_move": [
        _note("Delay the recapture", "any", "Before making an expected recapture, check whether a forcing move can be inserted first. A check, capture, or direct threat may improve the final exchange or change which piece survives.", ["zwischenzug", "move order", "forcing play"], 1, ["pending-recapture", "forcing-check", "loose-piece"]),
        _note("Intermediate check", "any", "An intermediate check is especially powerful because the opponent must respond before restoring material balance. Recalculate the resulting king position, pins, and overloaded defenders rather than returning automatically to the original exchange.", ["zwischenzug", "check", "overload"], 3, ["exposed-king", "pending-recapture", "pinned-defender"]),
        _note("Rook-check zwischenzug", "middlegame", "When a piece is expected to recapture in the center, a rook check on an open file can force the king to an awkward square before the exchange continues. The changed king placement may make the recapture tactically impossible.", ["zwischenzug", "rook check", "central exchange"], 5, ["open-e-file", "central-king", "pending-knight-recapture", "rook-on-open-file"]),
        _note("Threat between exchanges", "any", "A quiet intermediate threat can be stronger than a check when it traps a piece or attacks a more valuable target. Confirm that the opponent cannot answer with a stronger forcing move before postponing the recapture.", ["zwischenzug", "piece trap", "threat"], 4, ["restricted-piece", "pending-recapture", "higher-value-target"]),
    ],
    "motif.pin_and_skewer": [
        _note("Aligned-piece tactics", "any", "A pin restrains the front piece because moving it exposes something more valuable; a skewer forces the valuable front piece away and then wins the piece behind it. Look for aligned pieces on files, ranks, and diagonals.", ["pin", "skewer", "line tactics"], 1, ["aligned-pieces", "open-file", "open-diagonal"]),
        _note("Exploit absolute pin", "any", "Absolute pins against the king often allow the pinned piece to be captured or attacked again because it cannot legally move. Add pressure with the cheapest available attacker before releasing the pin.", ["absolute pin", "attacker buildup", "material gain"], 3, ["king-behind-piece", "pinned-minor-piece", "line-piece"]),
        _note("Rank skewer", "endgame", "A rook check along a rank can skewer an exposed king to an undefended rook or queen behind it. Check whether the king has a square that keeps protecting the rear piece before assuming the tactic wins material.", ["skewer", "rook check", "material gain"], 4, ["exposed-king", "aligned-rooks", "open-rank"]),
        _note("Open-file pin", "any", "A rook on an open file can pin a bishop or knight to the king, then capture the pinned piece after the defender runs out of interpositions. Count every possible block and king move before committing the rook.", ["pin", "rook tactic", "deflection"], 5, ["rook-on-open-file", "king-behind-minor-piece", "limited-interpositions"]),
    ],
    "motif.trapped_piece": [
        _note(
            "Zero safe mobility",
            "any",
            "- Count every safe escape square before leaving a piece short of flight squares.\n- A piece with zero safe replies will be lost once attacked with tempo.",
            ["motif.trapped_piece", "positional.restriction"],
            1,
            ["restricted-piece", "zero-safe-squares", "forcing-hunt"],
            slots={
                "worked": "their piece is already short of safe squares",
                "attention": "a piece still sits with no safe escape",
                "lesson": "count every flight square before the capture appears",
                "plan": "remove the remaining escapes, then take with the cheapest attacker",
            },
            conditions=[
                {"softKey": "motif.trapped_piece", "polarity": "any"},
                {"feature": "zero-safe-squares", "polarity": "any"},
            ],
        ),
        _note(
            "Net before capture",
            "middlegame",
            "- Quiet moves that remove escapes often matter more than the final take.\n- Especially against rim knights and edge rooks, build the net first.",
            ["motif.trapped_piece", "methodology.prophylactic_thinking"],
            3,
            ["edge-piece", "escape-square-removal", "delayed-capture"],
            slots={
                "worked": "the trapping net is already taking shape",
                "attention": "escape squares still need removing before the capture",
                "lesson": "calculate the trapping net before the capture appears on the board",
            },
            conditions=[
                {"softKey": "motif.trapped_piece", "polarity": "good"},
                {"feature": "delayed-capture", "polarity": "any"},
            ],
        ),
        _note(
            "Self-inflicted trap",
            "any",
            "- Do not push your own piece into a pocket with zero safe replies.\n- Seek an intermediate check or retreat before the net closes.",
            ["motif.trapped_piece", "methodology.candidate_moves"],
            2,
            ["self-trapped-piece", "hanging-after-push", "forcing-reply"],
            slots={
                "worked": "you avoided leaving a piece without flight squares",
                "attention": "your last move left a piece with no safe reply",
                "lesson": "do not push a piece into a pocket with zero safe escapes",
            },
            conditions=[
                {"softKey": "motif.trapped_piece", "polarity": "bad"},
                {"feature": "self-trapped-piece", "polarity": "bad"},
            ],
        ),
        _note(
            "Edge and corner nets",
            "middlegame",
            "- Rim knights and cornered bishops are the usual victims.\n- Cut retreats with pawns, then take with the cheapest attacker.",
            ["motif.trapped_piece", "imbalance.material_asymmetry"],
            4,
            ["rim-knight", "cornered-bishop", "pawn-net"],
            slots={
                "worked": "their rim piece is already short of retreats",
                "attention": "the edge piece still has one escape that must be cut",
                "lesson": "use pawns to cut retreats, then capture with the cheapest attacker",
            },
            conditions=[
                {"softKey": "motif.trapped_piece", "polarity": "good"},
                {"feature": "rim-knight", "polarity": "any"},
            ],
        ),
    ],
    "motif.sacrifice": [
        _note("Concrete compensation", "any", "A sacrifice exchanges material for concrete compensation such as king exposure, rapid development, a passed pawn, or a forcing attack. Judge it by the resulting position, not by the material count alone.", ["sacrifice", "compensation", "initiative"], 1, ["material-imbalance", "active-pieces", "exposed-king"]),
        _note("Forcing-line validation", "middlegame", "For an attacking sacrifice, calculate checks, captures, and threats until the defender reaches a stable position. If the attack ends without recovered material, a perpetual check, or a decisive positional gain, the sacrifice is probably unsound.", ["calculation", "king attack", "forcing play"], 3, ["exposed-king", "attacking-piece-majority", "limited-flight-squares"]),
        _note("Pawn for access", "middlegame", "A pawn sacrifice can open a file, clear an entry square, or distract a defender from the main wing. The best version gains tempi because accepting the pawn leaves the opponent unable to complete development or coordinate defense.", ["pawn sacrifice", "open lines", "deflection"], 2, ["closed-file", "overloaded-defender", "development-lead"]),
        _note("Exchange for passer", "endgame", "In a rook ending, sacrificing the rook for a dangerous passed pawn can be correct when the remaining pawns and king win the resulting pawn race. Calculate promotion squares, checking tempi, and whether the enemy king can stop your farthest passer.", ["rook sacrifice", "passed pawn", "pawn race"], 5, ["rook-versus-passed-pawn", "outside-passed-pawn", "active-king", "promotion-race"]),
    ],
    "opening.caro_kann": [
        _note("Build a sound center, complete development, and time the freeing break.", "opening", "The Caro-Kann Defence gives Black a sound pawn structure and usually a safe king. Black accepts slightly restrained development in return for a durable position, then challenges White's center with ...c5 or ...e5 and welcomes endgames in which few weaknesses remain.", ["sound development", "central break", "endgame"], 1, ["caro-kann structure", "d5-e6 pawn chain"], openings=["Caro-Kann Defence", "B12-B19"]),
        _note("Develop the potentially bad bishop outside the pawn chain.", "opening", "In the Caro-Kann, Black should solve the light-squared bishop before locking the center with ...e6 whenever possible. After that bishop reaches f5 or g4, the remaining pieces often develop compactly with ...Nd7, ...Ngf6, and ...Be7.", ["piece placement", "development", "bishop activity"], 2, ["light-squared bishop outside chain", "solid center"], openings=["Caro-Kann Defence", "B12-B19"]),
        _note("Attack a pawn chain at its base and challenge its head.", "middlegame", "Against the Caro-Kann Advance structure, Black attacks the base and head of White's e5-d4 chain with ...c5 and ...f6. White generally uses the space advantage for kingside play, while Black must avoid passive piece placement and strike before White consolidates.", ["pawn chain", "counterplay", "central tension"], 4, ["white e5-d4 chain", "c5 break", "f6 break"], openings=["Caro-Kann Defence", "Advance Variation", "B12"]),
        _note("Convert structural soundness into active endgame play.", "middlegame", "In Caro-Kann endgames, Black's structural health matters only if the pieces become active. Centralize the king, put rooks behind passed pawns, and do not trade automatically when the resulting minor-piece ending leaves a bishop tied to weaknesses.", ["simplification", "king activity", "passed pawn"], 5, ["sound pawn structure", "minor-piece ending"], openings=["Caro-Kann Defence", "B12-B19"], games=["Alexander Alekhine vs Jose Raul Capablanca 1927"]),
    ],
    "opening.english": [
        _note("Control the center with pieces before deciding the pawn structure.", "opening", "The English Opening controls the center from the flank and often delays a direct pawn occupation. White typically combines a kingside fianchetto with pressure on the long diagonal, then chooses between central expansion with d4 and queenside space with b4.", ["flank opening", "flexibility", "long diagonal"], 1, ["c4 pawn", "kingside fianchetto"], openings=["English Opening", "A10-A39"]),
        _note("Choose pawn breaks from the resulting structure, not the move order.", "opening", "English Opening positions often transpose, so plans matter more than labels. White should compare d4, e4, and b4 expansions; Black should decide whether to copy the queenside setup, occupy the center, or build a reversed Sicilian formation.", ["transposition", "pawn breaks", "strategic planning"], 2, ["flexible center", "reversed sicilian"], openings=["English Opening", "A20-A29"]),
        _note("Open the position when development and coordination favor you.", "middlegame", "In Symmetrical English structures, an early d4 break can open files before Black is fully coordinated, while a restrained setup may aim for b4-b5 and pressure on the queenside. A queen raid for loose pawns is dangerous when it loses time to rook lifts and discovered attacks.", ["symmetry", "queenside expansion", "development lead"], 4, ["symmetrical c-pawns", "d4 break", "b4-b5 break"], openings=["English Opening", "Symmetrical English", "A30-A39"]),
        _note("Use space to create an attack, but guard the holes it leaves.", "middlegame", "In Botvinnik-style English structures with pawns on c4 and e4, White gains space but weakens d4. The usual plan is to support kingside expansion with f4-f5 while a knight uses d5; Black seeks ...f5 or ...b5 and must challenge the fixed center before White's attack becomes organized.", ["space advantage", "outpost", "kingside attack"], 5, ["botvinnik structure", "d5 outpost", "f4-f5 break"], openings=["English Opening", "Botvinnik System", "A26"]),
    ],
    "opening.french": [
        _note("Attack the base of the opposing pawn chain.", "opening", "The French Defence creates a locked or semi-locked center in which each side attacks a pawn chain. White usually has more kingside space; Black develops counterplay against d4 with ...c5 and later challenges e5 with ...f6.", ["pawn chain", "counterplay", "space advantage"], 1, ["e5-d4 chain", "d5-e6 chain"], openings=["French Defence", "C00-C19"]),
        _note("Improve the bad bishop while attacking the center.", "middlegame", "French Defence strategy revolves around Black's light-squared bishop and timely pawn breaks. Black should not accept permanent passivity: improve the bishop through d7-e8-g6, b7-a6, or a later ...b6, and coordinate this with pressure on d4.", ["bad bishop", "piece maneuvering", "central pressure"], 2, ["closed center", "light-squared bishop behind chain"], openings=["French Defence", "C00-C19"]),
        _note("Use a closed center to transfer forces toward the king.", "middlegame", "In the French Advance, White can support a kingside attack with f4-f5, queen pressure on h5, and rook lifts along the third rank. These attacking ideas work best while the center stays closed; if Black breaks with ...f6 at the right moment, White's advanced e5-pawn can become a target.", ["kingside attack", "rook lift", "f-pawn break"], 4, ["advance french structure", "closed center", "e5 pawn"], openings=["French Defence", "Advance Variation", "C02"]),
        _note("Judge an isolated pawn by its activity, not only its weakness.", "middlegame", "When the French center transforms into an isolated d-pawn position, blockading d5 is not automatically enough. The defender must control the pawn's advance and the active squares behind it; exchanges favor the blockader only when they reduce the isolated pawn's dynamic support.", ["isolated pawn", "blockade", "simplification"], 5, ["isolated d5 pawn", "e5 blockade square"], openings=["French Defence", "C00-C19"]),
    ],
    "opening.italian": [
        _note("Complete development before opening the center.", "opening", "The Italian Game develops rapidly toward the center and kingside. In quieter lines, White builds with c3 and d3, prepares d4, and improves pieces before attacking; Black seeks equal central control and active breaks with ...d5 or ...b5.", ["development", "central break", "king safety"], 1, ["bishop on c4", "c3-d3 center"], openings=["Italian Game", "C50-C59"]),
        _note("Improve the least active piece while preserving the central break.", "opening", "Quiet Italian positions reward patient maneuvering. White often reroutes the queenside knight toward g3, places a rook on e1, and prepares d4 or kingside expansion; Black uses ...a6, ...Ba7, ...Re8, and ...d5 to prevent a lasting space disadvantage.", ["maneuvering", "piece improvement", "central tension"], 2, ["closed italian center", "d4 break", "d5 break"], openings=["Italian Game", "Giuoco Pianissimo", "C50-C54"]),
        _note("Retain attacking pieces when the opponent lacks counterplay.", "middlegame", "In Italian middlegames with tension on d4, White often keeps pieces on the board and aims them at Black's king rather than simplifying into equality. Black should contest the center and use the c-file or queenside expansion before White's h-pawn and g-pawn gain momentum.", ["kingside expansion", "central tension", "piece retention"], 4, ["d4 tension", "kingside pawn storm"], openings=["Italian Game", "C50-C54"], games=["Sooraj M R vs Cook, Philip 2026"]),
        _note("Improve every piece before converting an extra pawn.", "middlegame", "In Italian positions where White gains a queenside pawn, conversion depends on restraining counterplay rather than rushing to exchange. Knights can blockade and attack fixed pawns, while the king and rooks should activate before the extra pawn advances.", ["conversion", "blockade", "simplification"], 5, ["queenside pawn majority", "knight blockade"], openings=["Italian Game", "C50-C54"]),
    ],
    "opening.kings_indian": [
        _note("Allow space only when you can challenge its pawn base.", "opening", "The King's Indian Defence concedes central space so Black can attack it later. White usually expands on the queenside or in the center, while Black relies on the dark-squared bishop and breaks with ...e5 or ...c5 to generate dynamic counterplay.", ["counterattack", "space advantage", "dark-squared bishop"], 1, ["kingside fianchetto", "white pawn center"], openings=["King's Indian Defence", "E60-E99"]),
        _note("Attack on the wing indicated by your pawn chain.", "middlegame", "In closed King's Indian structures, the pawn chains point toward opposite wings. White commonly advances b4-b5 and attacks c7 or d6, while Black plays ...f5-f4 and transfers pieces toward the white king; speed and piece coordination outweigh small material gains.", ["opposite-wing attacks", "pawn chain", "initiative"], 2, ["locked center", "f5 break", "b4-b5 break"], openings=["King's Indian Defence", "Classical Variation", "E90-E99"]),
        _note("Create a second break when the first wing is sealed.", "middlegame", "Black's thematic ...f5 break in the King's Indian attacks e4 and can open the f-file. If the kingside remains closed, ...h5-h4 and a bishop transfer from g7 can create new entry points; if White blocks everything, Black should consider ...c6 and ...d5 to strike centrally.", ["f-pawn break", "file opening", "secondary break"], 4, ["e4 pawn base", "f-file", "g7 bishop"], openings=["King's Indian Defence", "E60-E99"]),
        _note("Use a passed pawn as a restraint before advancing it.", "middlegame", "King's Indian endgames can reverse the opening's attacking logic: once queens are gone, Black's king and dark-squared bishop must become active. A protected passed pawn can hold defenders in place while the king crosses the board to attack the queenside.", ["passed pawn", "king activity", "endgame transition"], 5, ["protected passed pawn", "active king", "dark-squared bishop"], openings=["King's Indian Defence", "E60-E99"]),
    ],
    "opening.london_system": [
        _note("Develop the bishop before closing its diagonal.", "opening", "The London System builds a reliable dark-square setup with the bishop developed before e3. White usually supports d4 with c3, develops the kingside safely, and then chooses between a central e4 break and kingside pressure.", ["system opening", "solid development", "central break"], 1, ["d4-c3-e3 triangle", "bishop on f4"], openings=["London System", "D02"]),
        _note("Use the system as a base, then adapt to the opponent's breaks.", "opening", "The London System is not only a fixed setup: White must react to Black's structure. Against ...c5 and ...Qb6, defend b2 efficiently and preserve central control; against a passive setup, use Ne5, Bd3, and e4 to gain space and attacking chances.", ["adaptation", "central control", "piece placement"], 2, ["b2 pressure", "e5 outpost", "e4 break"], openings=["London System", "D02"]),
        _note("Anchor an attack with an outpost, then bring every piece.", "middlegame", "In London middlegames, a knight on e5 supports direct play with Bd3, Qf3 or Qh5, and a kingside pawn advance. White should open lines only after enough pieces join the attack; Black should exchange the e5 knight or strike at d4 before the attack becomes self-sustaining.", ["kingside attack", "outpost", "piece coordination"], 4, ["e5 knight", "h-file pressure", "d4 pawn"], openings=["London System", "D02"]),
        _note("Combine a concrete threat with development and a central break.", "opening", "When Black plays an early ...Bf5 against the London System, White can challenge that bishop and use Qb3 to pressure b7. The point is not to hunt a pawn blindly, but to force awkward defense while preparing c4 or e4 and completing development.", ["queen pressure", "bishop challenge", "central expansion"], 5, ["pressure on b7", "black bishop on f5", "c4 break"], openings=["London System", "D02"]),
    ],
    "opening.petroff": [
        _note("Use symmetry to equalize development, not to copy moves blindly.", "opening", "The Petroff Defence meets White's central play symmetrically and aims for rapid development rather than passive defense. Early exchanges may reduce tactical danger, but both sides still compete for central activity and useful piece placement.", ["symmetry", "development", "central control"], 1, ["open e-file", "symmetrical center"], openings=["Petroff Defence", "C42-C43"]),
        _note("Preserve active pieces and earn equality with central play.", "middlegame", "Petroff positions often simplify into balanced middlegames, so small improvements matter. Centralize rooks, avoid exchanging an active developed piece for an undeveloped one without a reason, and use ...c6 and ...d5 to claim space when White's center permits it.", ["simplification", "piece activity", "central expansion"], 2, ["open files", "c6-d5 setup"], openings=["Petroff Defence", "C42-C43"]),
        _note("Prioritize initiative and king exposure over immediate material recovery.", "opening", "When White keeps the king in the center in a sharp Petroff branch, Black can use active bishop development and forcing rook pressure instead of rushing to recover material. A temporary pawn deficit is acceptable if ...c6 and ...d5 drive White's pieces back and open lines.", ["initiative", "king in center", "development tempo"], 4, ["temporary material imbalance", "c6-d5 pawn advance"], openings=["Petroff Defence", "C42"]),
        _note("Meet a sideline with development that creates a concrete problem.", "opening", "Against Petroff move-order sidelines, Black should preserve the defence's character without forcing a dubious imitation. A setup with ...Bb4 can pin the c3-knight and keep pressure on e4, while castling quickly ensures that tactical central play does not catch Black's king.", ["move order", "pin", "king safety"], 5, ["c3 knight pin", "e4 pressure"], openings=["Petroff Defence", "C42"], games=["Okhotnik, Vladimir vs Marta, Dominik 2026"]),
    ],
    "opening.queens_gambit": [
        _note("Use a wing pawn to undermine the opponent's center.", "opening", "The Queen's Gambit family uses the c-pawn to challenge Black's d5-pawn and build central influence. White seeks space and active development; Black chooses between holding the center, accepting temporarily, or creating a resilient Slav or Orthodox structure.", ["central pressure", "development", "pawn structure"], 1, ["d4-c4 center", "black d5 pawn"], openings=["Queen's Gambit", "D20-D69"]),
        _note("Trade dynamic pawn energy for activity before simplification.", "middlegame", "Queen's Gambit middlegames are defined by structure. In isolated-queen-pawn positions, the pawn grants activity and e5 access but may become weak after exchanges; in hanging-pawn positions, the side with the pawns should advance before they are blockaded.", ["isolated queen pawn", "hanging pawns", "piece activity"], 2, ["isolated d4 pawn", "c4-d4 hanging pawns"], openings=["Queen's Gambit", "D20-D69"]),
        _note("Answer a flank attack with active play in the center or opposite wing.", "middlegame", "In the Queen's Gambit Exchange Variation, White's minority attack with b4-b5 tries to create a fixed weakness on c6. Black should generate central or kingside activity before defending passively, often using ...Ne4, ...f5, or a timely ...c5 break.", ["minority attack", "counterplay", "weak pawn creation"], 4, ["carlsbad structure", "b4-b5 break", "c6 target"], openings=["Queen's Gambit Declined", "Exchange Variation", "D35-D36"]),
        _note("Do not defend a gambit pawn at the cost of development.", "opening", "In Queen's Gambit Accepted structures, Black usually returns the c4-pawn rather than spending time trying to keep it. The strategic goal is rapid development and a central ...c5 or ...e5 break; White uses the temporary lead in space to recover the pawn without allowing Black full coordination.", ["gambit pawn", "rapid development", "central break"], 5, ["temporary c4 pawn", "open center"], openings=["Queen's Gambit Accepted", "D20-D29"]),
    ],
    "opening.ruy_lopez": [
        _note("Create central pressure while keeping development flexible.", "opening", "The Ruy Lopez increases pressure on Black's e5-pawn while preserving flexible central play. White often builds slowly with c3 and d4; Black seeks active development, queenside space, and a timely ...d5 break rather than merely defending e5.", ["central pressure", "development", "pawn break"], 1, ["bishop on b5", "e5 pawn", "c3-d4 plan"], openings=["Ruy Lopez", "C60-C99"]),
        _note("Use closed centers to reroute pieces toward their best squares.", "middlegame", "Closed Ruy Lopez positions reward long maneuvers because the center restricts immediate tactics. White may reroute the queenside knight through d2-f1-g3 and prepare d4 or a kingside attack; Black expands with ...a6 and ...b5 and searches for ...d5 or queenside counterplay.", ["maneuvering", "piece placement", "queenside expansion"], 2, ["closed spanish center", "knight maneuver", "b5 pawn"], openings=["Ruy Lopez", "Closed Spanish", "C84-C99"], games=["Slim Bouaziz vs Alexander Beliavsky 1987"]),
        _note("Evaluate exchanges by the resulting pawn ending and piece activity.", "middlegame", "In the Exchange Ruy Lopez, White can accept the bishop pair to damage Black's queenside pawns and aim for a favorable king-and-pawn ending. Black's compensation is active bishops and open lines, so White should not exchange automatically before restraining that activity.", ["bishop pair", "pawn majority", "endgame transition"], 4, ["doubled c-pawns", "kingside pawn majority"], openings=["Ruy Lopez", "Exchange Variation", "C68-C69"]),
        _note("When defending a gambit, reduce coordination before consolidating material.", "middlegame", "In Marshall-style Ruy Lopez positions, Black sacrifices a pawn to accelerate development and attack the white king. White's defensive task is to neutralize coordinated queen, bishop, and rook threats; material matters only after escape squares are secured and the attacking pieces are exchanged.", ["gambit attack", "king safety", "defensive simplification"], 5, ["open e-file", "black attacking initiative"], openings=["Ruy Lopez", "Marshall Attack", "C89"]),
    ],
    "opening.scandinavian": [
        _note("Accept a tempo loss only for a clear structural goal.", "opening", "The Scandinavian Defence challenges White's e4-pawn immediately and forces an early central exchange. Black accepts some loss of time with the queen in exchange for a clear structure, then aims to complete development and strike at White's center.", ["early central challenge", "queen development", "pawn structure"], 1, ["open d-file", "white central space"], san_lines=["1. e4 d5 2. exd5 Qxd5"], openings=["Scandinavian Defence", "B01"]),
        _note("Use the open bishop diagonal before fixing the pawn chain.", "opening", "Scandinavian structures often resemble the Caro-Kann or Slav: Black develops the light-squared bishop before ...e6 and builds a compact position. The main freeing ideas are ...c5 and ...e5, while careless queen moves can leave Black behind in development.", ["bishop development", "central break", "tempo"], 2, ["caro-slav structure", "bishop outside chain"], openings=["Scandinavian Defence", "B01"]),
        _note("Place the queen where it supports breaks without blocking development.", "opening", "In ...Qd6 Scandinavian setups, Black's queen supports e5 and kingside castling but can obstruct the dark-squared bishop. Black should coordinate ...c6, ...Qc7 or ...Qc7-like regrouping, and ...e5 without allowing White to gain tempi through Bf4 or Ne4.", ["queen placement", "piece coordination", "e5 break"], 4, ["queen on d6", "c6 support", "central break"], openings=["Scandinavian Defence", "Gubinsky-Melts Defence", "B01"]),
        _note("Blockade a passed pawn before it reaches the sixth rank.", "middlegame", "Scandinavian endgames can favor Black when the opening's early exchange leaves a sound, easy-to-defend structure. Still, passed pawns must be blockaded actively: the king and knight should reach central squares before an advanced pawn forces a bishop sacrifice at promotion.", ["passed pawn", "blockade", "endgame"], 5, ["central passed pawn", "minor-piece ending"], openings=["Scandinavian Defence", "B01"]),
    ],
    "opening.sicilian": [
        _note("Use structural imbalance to create counterplay.", "opening", "The Sicilian Defence creates an asymmetrical fight: Black exchanges the c-pawn for White's d-pawn and gains a central pawn majority, while White receives space and faster kingside development. Both sides must seek active play because the structure rarely rewards passivity.", ["asymmetry", "counterplay", "central majority"], 1, ["semi-open c-file", "black central pawn majority"], openings=["Sicilian Defence", "B20-B99"]),
        _note("Attack where your open files and pawn levers point.", "middlegame", "Open Sicilian middlegames often feature opposite-wing attacks. White uses the f-pawn, g-pawn, and pieces against Black's king, while Black presses along the c-file and expands with ...b5-b4; development speed and forcing moves matter more than collecting loose pawns.", ["opposite-wing attacks", "open file", "initiative"], 2, ["open c-file", "queenside pawn storm", "kingside pawn storm"], openings=["Sicilian Defence", "Open Sicilian", "B30-B99"]),
        _note("Choose recaptures by king safety and square control, not pawn shape alone.", "middlegame", "In Najdorf English Attack structures, White often castles queenside and advances f3, g4, and h4, while Black counters with ...b5-b4 and pressure on c3. Recapturing on b3 with the a-pawn can protect the castled king and deny Black a c4 outpost, even at the cost of doubled pawns.", ["english attack", "opposite-side castling", "recapture choice"], 4, ["najdorf structure", "a-file reinforcement", "c4 square"], openings=["Sicilian Defence", "Najdorf English Attack", "B90"], games=["Wandor, Adam vs Iwan, Patryk 2026"]),
        _note("In a cramped position, prepare one freeing break with every piece.", "middlegame", "Against a Maroczy Bind, Black has less space but can build a Hedgehog with pawns on a6, b6, d6, and e6. The position comes alive through ...b5 or ...d5; Black should prepare these breaks patiently, while White must improve pieces and prevent liberation without overextending.", ["maroczy bind", "hedgehog", "freeing break"], 5, ["hedgehog structure", "white c4-e4 bind", "b5 break", "d5 break"], openings=["Sicilian Defence", "Maroczy Bind", "B36-B38"]),
    ],
    "piece.blockade": [
        _note("Restrain first, attack second", "middlegame", "A blockade stops a passed or isolated pawn and turns it into a target. Choose a blockader that can remain stable without becoming passive.", ["blockade", "pawn structures"], 1, ["passed pawn", "isolated pawn"]),
        _note("Match the blockader to the phase", "endgame", "Knights are often ideal blockaders because they can attack while occupying the square in front of the pawn. Kings and bishops become effective blockaders in simplified endings.", ["blockade", "piece activity"], 3, ["knight blockader", "king activity", "bishop coordination"], games=["Baryshpolets vs Turov 2012"]),
        _note("Coordinate the blockade against multiple passers", "endgame", "Against connected or doubled passers, establish the blockade before they advance with tempo. Centralize the king or bishop so it stops the lead pawn, guards the second passer, and releases a rook from defensive duty.", ["blockade", "doubled pawns", "passed pawn"], 5, ["connected passers", "lead pawn", "rook activity"], games=["Alexander Alekhine vs Jose Raul Capablanca 1927"]),
    ],
    "piece.centralization": [
        _note("Use the center to increase reach", "all", "Centralized pieces influence both wings and can switch tasks quickly. In endgames, the king should usually join the center as soon as tactics permit.", ["centralization", "piece activity"], 1, ["central squares"]),
        _note("Centralize with a concrete function", "middlegame", "Centralization is valuable when it supports a pawn break, attacks a weakness, or escorts a passer. Do not centralize mechanically if the destination can be driven away with tempo.", ["centralization", "pawn break", "passed pawn"], 3, ["tempo", "weakness"], openings=["English Opening"]),
        _note("Centralize king and rook around the passer", "endgame", "In a rook-and-pawn ending, place the king diagonally ahead of the passer when possible, support the pawn with the rook after it is attacked, and advance only when both pieces remain coordinated.", ["centralization", "rook ending", "passed pawn"], 5, ["active king", "rook support", "passed pawn"], games=["Alexander Alekhine vs Jose Raul Capablanca 1927"]),
    ],
    "piece.coordination": [
        _note(
            "Make every piece serve the plan",
            "any",
            "- Coordinate pieces so they cover one another and share one plan.\n- Improve the piece that cannot yet change roles without losing key squares.",
            ["piece.coordination", "piece.centralization"],
            1,
            ["shared-plan", "mutual-coverage", "key-squares"],
            slots={
                "worked": "your pieces already support one shared plan",
                "attention": "at least one piece still fails to cover the others or the plan",
                "lesson": "make every piece serve the same plan and cover the others",
                "plan": "improve the least useful piece before inventing a new attack",
            },
            conditions=[
                {"softKey": "piece.coordination", "polarity": "any"},
                {"metric": "mobility", "polarity": "any"},
                {"metric": "open_file_utilization", "polarity": "any"},
            ],
        ),
        _note(
            "Coordinate pieces around the passer",
            "endgame",
            "- Escort a passer while controlling its blockade square.\n- Material matters less than whether the army can advance without counterplay.",
            ["piece.coordination", "structure.passed_pawn"],
            3,
            ["blockade-squares", "counterplay", "passed-pawn"],
            slots={
                "worked": "pieces already escort the passer productively",
                "attention": "the passer still lacks coordinated escort and blockade control",
                "lesson": "coordinate pieces around the passer before pushing it",
            },
            conditions=[
                {"softKey": "piece.coordination", "polarity": "good"},
                {"softKey": "structure.passed_pawn", "polarity": "any"},
            ],
        ),
        _note(
            "Assign complementary escorting roles",
            "endgame",
            "- Give each piece a task before pushing connected passers.\n- One covers the blockader, one stops checks, one attacks the defender.",
            ["piece.coordination", "structure.passed_pawn"],
            5,
            ["blockading-square", "checks", "minor-piece-placement"],
            slots={
                "worked": "roles around the passers are already clear",
                "attention": "connected passers still need complementary escorting roles",
                "lesson": "assign each piece a task before advancing connected passers",
            },
            conditions=[
                {"softKey": "piece.coordination", "polarity": "bad"},
                {"feature": "blockading-square", "polarity": "any"},
            ],
        ),
    ],
    "piece.rerouting": [
        _note("Improve the least useful piece", "middlegame", "When a piece has no useful targets, reroute it toward a stable square that supports the position's main break or restrains the opponent's plan.", ["piece rerouting", "piece activity"], 1, []),
        _note("Prefer maneuvering over needless pawn moves", "middlegame", "In symmetrical structures, patient rerouting is often stronger than creating unnecessary pawn weaknesses. Judge the route by destination, tempi, and tactical safety.", ["piece rerouting", "symmetrical pawn structures"], 3, ["weak squares", "tempi"], openings=["Petroff Defense"]),
        _note("Reroute without abandoning tactical duties", "middlegame", "A knight stranded on the flank or tied to a pawn can often return through the back rank to a central support square. Verify that moving it does not release a capture or remove control of a key recapture square.", ["piece rerouting", "knight maneuvering", "calculation"], 5, ["back-rank route", "recapture square", "pawn tension"], openings=["Petroff Defense"], games=["Baryshpolets vs Turov 2012"]),
    ],
    "piece.seventh_rank_invasion": [
        _note("Invade where pawns and king are vulnerable", "middlegame", "A rook on the seventh rank attacks pawns from the side, restricts the king, and often creates mating or promotion threats.", ["seventh rank", "rook activity"], 1, ["weak pawns", "restricted king"]),
        _note("Coordinate the seventh-rank entry", "endgame", "An invasion is strongest when another piece controls the escape squares or a passed pawn distracts the defender. Prepare entry by taking an open file and denying exchanges.", ["seventh rank", "passed pawn", "piece coordination"], 3, ["open file", "escape squares"], games=["Baryshpolets vs Turov 2012"]),
        _note("Use king entry and deflection to invade", "endgame", "In a rook ending, combine a seventh-rank rook with an advancing king that attacks the defender's pawns. If entry is blocked, a pawn sacrifice can open the file or deflect the guarding rook.", ["seventh rank", "rook ending", "simplification"], 5, ["active king", "deflection", "pawn sacrifice"], games=["Alexander Alekhine vs Jose Raul Capablanca 1927"]),
    ],
    "piece.simplification": [
        _note("Exchange activity, not merely material", "all", "Simplify when exchanges preserve your advantage and remove the opponent's active resources. Trading pieces is not automatically good just because you are ahead.", ["simplification", "decision making"], 1, []),
        _note("Preserve the favorable piece matchup", "middlegame", "Trade your bad minor piece for the opponent's good one, or exchange attackers when defending. Keep the pieces that can exploit the remaining pawn structure.", ["simplification", "good bishop", "bad bishop"], 3, ["minor-piece trade", "pawn structure"], games=["Mark Taimanov vs Miguel Najdorf 1953"]),
        _note("Evaluate the exact ending before exchanging", "endgame", "Before entering a pawn ending, verify king access, reserve tempi, and pawn breaks. A favorable-looking exchange can fail if the resulting isolated pawn is fixed or the opponent creates a distant passer.", ["simplification", "pawn ending", "calculation"], 5, ["king access", "reserve tempi", "isolated pawn", "distant passer"], games=["Alexander Alekhine vs Jose Raul Capablanca 1927"]),
    ],
    "positional.color_complexes": [
        _note("Exploit permanently weak colors", "middlegame", "Pawn moves permanently weaken squares of one color. Coordinate pieces to occupy those squares, especially when the opponent lacks the bishop that could contest them.", ["color complexes", "piece coordination"], 1, ["weak squares", "missing bishop"]),
        _note("Read color weaknesses from structure", "middlegame", "Judge a color complex through the pawn structure and bishop placement, not the exact position alone. A fixed pawn can become a target when it sits on its own bishop's color.", ["color complexes", "pawn structures", "good bishop", "bad bishop"], 3, ["fixed pawn", "bishop placement"], games=["Sandro Mareco vs Jorge Cori 2009"]),
        _note("Coordinate an attack on the weakened complex", "middlegame", "When kingside pawns are fixed on dark squares and the dark-squared bishop is absent, build a queen-and-bishop or queen-and-knight attack on the entry squares. First give your own king a flight square so tactics do not reverse the attack.", ["color complexes", "king safety", "piece coordination"], 5, ["fixed kingside pawns", "flight square", "entry squares"], openings=["French Defense"], games=["Alexander Alekhine vs Jose Raul Capablanca 1927"]),
    ],
    "positional.outpost": [
        _note("Convert a stable square into activity", "middlegame", "An outpost is a useful square that cannot be challenged safely by an enemy pawn. Occupy it with a piece that creates concrete threats.", ["outpost", "piece activity"], 1, ["pawn control"]),
        _note("Match the outpost to the right piece", "middlegame", "Pawn structure determines outposts. A supported knight is especially strong when it attacks weaknesses on both wings and cannot be exchanged by the opponent's favorable minor piece.", ["outpost", "pawn structures", "minor piece battles"], 3, ["supported knight", "weak pawns"], games=["Sandro Mareco vs Jorge Cori 2009"]),
        _note("Secure and activate the outpost", "middlegame", "Before installing a knight on a central outpost, prevent the pawn break that would undermine its support and compare the opponent's exchange options. If the knight also blocks an IQP, it should pressure adjacent squares rather than become a passive guard.", ["outpost", "IQP", "blockade"], 5, ["central knight", "support pawn", "undermining break"], openings=["Queen's Gambit"], games=["Alexander Alekhine vs Jose Raul Capablanca 1927"]),
    ],
    "positional.pawn_break": [
        _note(
            "Break with a structural purpose",
            "middlegame",
            "- Prepare the break with pieces before changing the structure.\n- The lever should open a line, challenge a chain, or gain a useful square.",
            ["positional.pawn_break", "imbalance.space", "piece.coordination"],
            1,
            ["pawn-lever", "open-line", "useful-square"],
            slots={
                "worked": "a timely pawn break already improved the structure",
                "attention": "the freeing pawn break still needs preparation",
                "lesson": "break only with a structural purpose and piece support",
                "plan": "prepare the lever, then open the line your pieces can use",
            },
            conditions=[
                {"softKey": "positional.pawn_break", "polarity": "any"},
                {"metric": "center_fluidity_index", "polarity": "any"},
                {"feature": "pawn-lever", "polarity": "any"},
            ],
        ),
        _note(
            "Target the vulnerable point of the chain",
            "middlegame",
            "- Decide whether the head or base of the chain is the real target.\n- Choose the lever that opens files for your better-coordinated pieces.",
            ["positional.pawn_break", "structure.pawn_chain", "piece.coordination"],
            3,
            ["chain-head", "chain-base", "open-file"],
            slots={
                "worked": "you already challenged the weak point of their chain",
                "attention": "the chain still needs a lever at its true weak point",
                "lesson": "attack the head or base that opens files for your pieces",
            },
            conditions=[
                {"softKey": "positional.pawn_break", "polarity": "bad"},
                {"softKey": "structure.pawn_chain", "polarity": "any"},
            ],
        ),
        _note(
            "Time or restrain the hanging-pawn break",
            "middlegame",
            "- With hanging pawns, advance only while both are defended and pieces can use the lines.\n- Against them, restrain the advance, provoke one forward, then attack the weakness left behind.",
            ["positional.pawn_break", "structure.hanging_pawns"],
            5,
            ["central-advance", "opened-lines", "backward-weakness"],
            slots={
                "worked": "hanging-pawn tension is already under control",
                "attention": "the hanging-pawn advance still needs timing or restraint",
                "lesson": "time the hanging-pawn break only with full defence and open-line follow-up",
            },
            conditions=[
                {"softKey": "positional.pawn_break", "polarity": "any"},
                {"feature": "central-advance", "polarity": "any"},
            ],
        ),
    ],
    "positional.prophylaxis": [
        _note("Stop plans before threats appear", "all", "Prophylaxis means preventing the opponent's plan before it becomes a direct threat. Look first for their intended pawn break and best improving move.", ["prophylaxis", "strategic planning"], 1, []),
        _note("Restrain the freeing lever", "middlegame", "In a familiar structure, identify the lever that releases the opponent's cramped pieces. Control its preparation square while improving your own worst-placed piece.", ["prophylaxis", "pawn structures", "restriction"], 3, ["pawn lever", "cramped pieces"], games=["Baryshpolets vs Turov 2012"]),
        _note("Apply structure-specific prophylaxis", "middlegame", "Against an IQP, prevent the liberating advance before piling up on the pawn. Against a Carlsbad minority attack, slow the b-pawn lever and keep enough coordination to meet a switch to the kingside.", ["prophylaxis", "IQP", "Carlsbad"], 5, ["liberating advance", "minority attack", "wing switch"], openings=["Queen's Gambit"], games=["Alexander Alekhine vs Jose Raul Capablanca 1927"]),
    ],
    "positional.restriction": [
        _note("Remove counterplay before converting", "middlegame", "Restriction reduces the opponent's useful moves before you attack. Control freeing squares and breaks, then improve your pieces without releasing their position.", ["restriction", "domination"], 1, []),
        _note("Preserve the structure that creates space", "middlegame", "A spatial advantage matters when the pawn structure denies good squares to enemy pieces. Avoid exchanges that free a cramped defender unless the resulting ending is clearly favorable.", ["restriction", "space advantage", "pawn structures"], 3, ["cramped pieces", "piece exchanges"], openings=["Caro-Kann Defense"]),
        _note("Build domination around a key square", "middlegame", "If control of e5 dominates the position, reinforce that square, neutralize the defender that contests it, and stop the freeing pawn break. Then redirect the least active piece toward the fixed weakness created by the restriction.", ["restriction", "outpost", "piece rerouting"], 5, ["e5 outpost", "freeing break", "fixed weakness"], openings=["Queen's Gambit"], games=["Baryshpolets vs Turov 2012"]),
    ],
    "positional.two_weaknesses": [
        _note("Stretch the defense across two fronts", "endgame", "One weakness can often be defended. Create or attack a second weakness far away so the defender cannot coordinate against both.", ["two weaknesses", "endgame technique"], 1, []),
        _note("Fix, restrict, then switch", "endgame", "Fix the first target before switching wings. Calm improving moves and prophylaxis force passive defense, making the later transfer of king and pieces more effective.", ["two weaknesses", "prophylaxis", "piece maneuvering"], 3, ["fixed target", "wing switch"], games=["Mark Taimanov vs Miguel Najdorf 1953"]),
        _note("Preserve pressure while creating distance", "endgame", "When a kingside pawn is already weak, provoke a queenside pawn into becoming a second target. Keep rooks on the board if exchanging them would let the king defend both weaknesses comfortably, and centralize your king before switching fronts.", ["two weaknesses", "rook ending", "king activity"], 5, ["kingside weakness", "queenside target", "rook exchange"], games=["Alexander Alekhine vs Jose Raul Capablanca 1927"]),
    ],
    "structure.carlsbad": [
        _note("Let the Carlsbad structure choose the wing", "middlegame", "In the Carlsbad structure, plans come from the fixed central pawn skeleton: a queenside minority attack, central expansion, or a kingside initiative.", ["Carlsbad", "pawn structures"], 1, ["fixed center"], openings=["Queen's Gambit Exchange"]),
        _note("Create a queenside target with the minority", "middlegame", "The minority attack uses fewer queenside pawns to provoke a backward or isolated pawn. Its value depends on open files and piece coordination, not on mechanically pushing pawns.", ["Carlsbad", "minority attack"], 3, ["queenside majority", "backward pawn", "open file"], openings=["Queen's Gambit Exchange"], games=["Alexander Alekhine vs Jose Raul Capablanca 1927"]),
        _note("Coordinate pieces before the minority break", "middlegame", "Before the Carlsbad b-pawn break, place rooks on the files likely to open and ensure a knight can occupy the weakened c5 or c6 square. If the opponent starts a kingside attack, compare speed rather than assuming the minority attack remains correct.", ["Carlsbad", "minority attack", "piece coordination"], 5, ["b-pawn lever", "c-file", "outpost", "opposite-wing play"], openings=["Queen's Gambit Exchange"], games=["Baryshpolets vs Turov 2012"]),
    ],
    "structure.caro_slav": [
        _note("Challenge the advanced d-pawn", "middlegame", "The Caro-Slav family is defined by one side's advanced d-pawn against a restrained opposing center. Plans revolve around challenging that pawn and freeing the cramped pieces behind it.", ["Caro-Slav", "pawn structures"], 1, ["advanced d-pawn", "cramped pieces"], openings=["Caro-Kann Defense", "Slav Defense"]),
        _note("Choose the correct structural lever", "middlegame", "In Caro-Slav structures, compare breaks against the front of the chain with breaks against its base. Piece placement decides whether the position opens favorably or leaves a permanent weak pawn.", ["Caro-Slav", "pawn break", "piece coordination"], 3, ["chain head", "chain base", "weak pawn"], openings=["Caro-Kann Defense", "Slav Defense"], games=["Volodin, Alexandr E. vs Riazantsev, Alexander 2026"]),
        _note("Release pieces trapped by your own pawn", "middlegame", "If an advanced e-pawn merely blocks your bishop and rook, returning or sacrificing it can restore coordination. Do not attack a distant pawn while the opponent has a protected passer or a forcing kingside advance.", ["Caro-Slav", "piece coordination", "passed pawn"], 5, ["advanced e-pawn", "blocked bishop", "rook activity", "protected passer"], openings=["Slav Defense"], games=["Maltsevskaya, Aleksandra vs Subelj, Jan 2026"]),
    ],
    "structure.doubled_pawns": [
        _note("Judge doubled pawns by function", "all", "Doubled pawns are weaknesses only when they can be attacked or cannot create useful control. They may open files, guard key squares, and restrain an enemy majority.", ["doubled pawns", "pawn structures"], 1, ["open file", "square control"]),
        _note("Fix and blockade the doubled pawns", "endgame", "In an ending, fix doubled pawns before attacking them. A blockade on the rank ahead can stop both pawns while active pieces target the base.", ["doubled pawns", "blockade", "endgame technique"], 3, ["fixed pawns", "base pawn"], games=["Alexander Alekhine vs Jose Raul Capablanca 1927"]),
        _note("Preserve useful doubled pawns", "endgame", "Do not repair doubled kingside pawns automatically if they still halt an enemy majority and remain easy for the king to defend. Exchange only when the resulting open file, passer, or king entry clearly favors you.", ["doubled pawns", "king activity", "passed pawn"], 5, ["kingside majority", "open file", "king entry"], openings=["Ruy Lopez"], games=["Baryshpolets vs Turov 2012"]),
    ],
    "structure.dragon_formation": [
        _note("Activate the fianchetto against the center", "middlegame", "The Dragon formation features a kingside fianchetto aimed at a center that may open. Its strength comes from the long diagonal and coordinated counterplay.", ["Dragon formation", "pawn structures"], 1, ["kingside fianchetto", "long diagonal"], openings=["Sicilian Dragon"]),
        _note("Recognize the structure beyond the opening", "middlegame", "Dragon positions should be recognized by structure even with colors reversed. Compare central pawn tension, access to the long diagonal, and which side can open lines first.", ["Dragon formation", "piece coordination"], 3, ["reversed colors", "central tension", "long diagonal"], openings=["Sicilian Dragon", "English Opening"], games=["Folin, Giorgio vs Picone Chiodo, Luigi 2026"]),
        _note("Prepare the Dragon's freeing break", "middlegame", "Against a Maróczy-style bind, the Dragon bishop needs a pawn break to become active. Coordinate the queen, rook, and knight behind the freeing break; an unsupported push only creates targets while the opponent controls the central light squares.", ["Dragon formation", "Maróczy Bind", "pawn break"], 5, ["fianchetto bishop", "central light squares", "freeing break"], openings=["Accelerated Dragon"], games=["Wandor, Adam vs Iwan, Patryk 2026"]),
    ],
    "structure.hanging_pawns": [
        _note("Use activity before hanging pawns become weak", "middlegame", "Hanging pawns offer space and dynamic breaks but can become fixed targets. Their value depends on whether they can advance while pieces remain coordinated.", ["hanging pawns", "pawn structures"], 1, ["space", "dynamic breaks"]),
        _note("Advance or restrain the hanging pair", "middlegame", "The side with hanging pawns should prepare a central advance or kingside activity. The defender should restrain both pawns, provoke one forward, and attack the remaining weakness.", ["hanging pawns", "restriction", "pawn break"], 3, ["central advance", "fixed target"], openings=["Queen's Gambit"], games=["Sandro Mareco vs Jorge Cori 2009"]),
        _note("Transform hanging pawns before simplification", "middlegame", "Before simplifying a hanging-pawn position, check whether exchanges remove the pieces that support the central break. With fewer minor pieces, the defender can often blockade the pawns; the owner may need to create a passed d-pawn before that blockade is secure.", ["hanging pawns", "simplification", "passed pawn"], 5, ["minor-piece exchanges", "blockade", "passed d-pawn"], openings=["Queen's Gambit"], games=["Alexander Alekhine vs Jose Raul Capablanca 1927"]),
    ],
    "structure.hedgehog": [
        _note("Store energy behind the Hedgehog shell", "middlegame", "The Hedgehog accepts less space in return for a compact pawn shell and prepared counterbreaks. Patience and piece coordination matter more than immediate activity.", ["Hedgehog", "pawn structures"], 1, ["compact setup", "space disadvantage"], openings=["Sicilian Defense"]),
        _note("Prepare or prevent the freeing breaks", "middlegame", "The Hedgehog player seeks freeing central or queenside breaks; the space-advantaged side restrains them and improves pieces without overextending.", ["Hedgehog", "prophylaxis", "pawn break"], 3, ["central break", "queenside break", "space advantage"], openings=["Sicilian Defense"], games=["Folin, Giorgio vs Picone Chiodo, Luigi 2026"]),
        _note("Coordinate and reassess Hedgehog counterplay", "middlegame", "In a Hedgehog, place rooks and queen behind the central breaks and reroute a knight toward active kingside or central squares. If the opponent controls the key break square, switch plans efficiently instead of spending more tempi on an impossible push.", ["Hedgehog", "piece rerouting", "candidate moves"], 5, ["central break", "rook coordination", "knight route", "tempi"], openings=["Sicilian Defense"], games=["Wandor, Adam vs Iwan, Patryk 2026"]),
    ],
    "structure.iqp": [
        _note("Use IQP activity before simplification", "middlegame", "An IQP grants space, open lines, and active piece play, but becomes a long-term target if its advance is stopped and pieces are exchanged.", ["IQP", "pawn structures"], 1, ["isolated d-pawn", "open lines"]),
        _note("Advance the IQP or build the blockade", "middlegame", "The IQP side should coordinate pieces for the liberating advance or a kingside attack. The defender should blockade the pawn, exchange active pieces, and pressure the pawn from front and side.", ["IQP", "blockade", "simplification"], 3, ["liberating advance", "kingside attack", "isolated d-pawn"], openings=["Queen's Gambit Accepted"], games=["Diak, Hryhorii vs Kovalenko, Daniil D. 2026"]),
        _note("Prepare the IQP break tactically", "middlegame", "Before advancing an IQP, unpin the supporting knight and prevent the opponent's favorable bishop development or blockade. The push is strongest when it opens diagonals with tempo and leaves no weak pawn behind.", ["IQP", "piece coordination", "pawn break"], 5, ["pinned knight", "bishop development", "open diagonal"], openings=["Queen's Gambit Accepted"], games=["Dardha, Daniel vs Sumets, Andrey 2026"]),
    ],
    "structure.maroczy_bind": [
        _note("Convert space by maintaining the bind", "middlegame", "The Maróczy Bind uses central pawns to restrict freeing breaks and limit opposing pieces. Its owner should improve patiently without loosening the bind.", ["Maróczy Bind", "restriction"], 1, ["central space", "restricted breaks"], openings=["Accelerated Dragon"]),
        _note("Control the breaks that challenge the bind", "middlegame", "The cramped side seeks timely pawn breaks and piece exchanges; the side with the Maróczy Bind controls those breaks and targets backward pawns created by the compact setup.", ["Maróczy Bind", "pawn break", "restriction"], 3, ["backward pawn", "space advantage"], openings=["Accelerated Dragon"], games=["Folin, Giorgio vs Picone Chiodo, Luigi 2026"]),
        _note("Coordinate the bind against the freeing break", "middlegame", "A knight reroute toward a stable queenside or central square can reinforce the Maróczy Bind while freeing heavier pieces. Before allowing the opponent's f-pawn break, calculate whether the opened diagonal activates the Dragon bishop or merely leaves lasting weaknesses.", ["Maróczy Bind", "piece rerouting", "Dragon formation"], 5, ["knight outpost", "f-pawn break", "fianchetto bishop"], openings=["Accelerated Dragon"], games=["Wandor, Adam vs Iwan, Patryk 2026"]),
    ],
    "structure.passed_pawn": [
        _note("Use the passer to restrict defenders", "endgame", "A passed pawn is valuable because it demands a blockade and ties down pieces. Support it with active pieces rather than pushing it automatically.", ["passed pawn", "endgame technique"], 1, ["blockade"]),
        _note("Create and escort the passer", "endgame", "Create a passed pawn by fixing the opposing majority, opening the correct file, or forcing a favorable exchange. The farther advanced the passer, the more urgently pieces must coordinate around it.", ["passed pawn", "piece coordination"], 3, ["pawn majority", "open file", "advanced passer"], games=["Sandro Mareco vs Jorge Cori 2009"]),
        _note("Coordinate blockade and diversion", "endgame", "Against a passed pawn, establish the blockade with the king or bishop before attacking its base. As the stronger side, prevent counterplay on the opposite wing, escort the pawn from behind or beside it, and use a second weakness to overload the blockader.", ["passed pawn", "blockade", "two weaknesses"], 5, ["king blockader", "bishop blockader", "opposite-wing counterplay"], games=["Alexander Alekhine vs Jose Raul Capablanca 1927"]),
    ],
    "structure.pawn_chain": [
        _note("Attack the pawn chain at its support", "middlegame", "In a locked center, pawn chains determine space, breaks, and piece routes. Attack the base or undermine the head rather than pushing without a target.", ["pawn chain", "locked center"], 1, ["chain base", "chain head"], openings=["French Defense", "Caro-Kann Defense"]),
        _note("Coordinate the wing attack with the chain", "middlegame", "A closed center gives time to reroute pieces toward the wing where the chain points. Prepare the pawn lever that opens lines for those pieces while slowing the opponent's lever.", ["pawn chain", "piece rerouting", "pawn break"], 3, ["closed center", "wing play"], openings=["French Defense"], games=["Surkeev, Shumkar vs Fakhriddinxujaev, Umarxon 2026"]),
        _note("Choose the lever by resulting lines", "middlegame", "When one lever attacks the front pawn and another attacks the base, compare which exchange opens the useful diagonal or file. A flank pawn push can be correct if it fixes the defender or removes support from the entire chain.", ["pawn chain", "pawn break", "color complexes"], 5, ["front pawn", "base pawn", "open diagonal", "open file"], openings=["French Defense"], games=["Naidon, Pietro Weber vs Born, Ary 2026"]),
    ],
    "structure.scheveningen": [
        _note("Balance compact defense with timely counterplay", "middlegame", "The Scheveningen small center is flexible but compact. Black prepares central counterplay while White uses space for a kingside attack or pressure on the queenside.", ["Scheveningen", "small center"], 1, ["compact center", "space advantage"], openings=["Sicilian Scheveningen"]),
        _note("Identify Scheveningen plans by structure", "middlegame", "Recognize the Scheveningen by the central pawn structure, whether reached from the Najdorf, Kan, or Taimanov. Plans depend more on the breaks and piece coordination than the move order.", ["Scheveningen", "pawn structures", "transposition"], 3, ["central pawns", "pawn breaks"], openings=["Sicilian Scheveningen", "Sicilian Najdorf"], games=["Sadhwani, Raunak vs Lu, Shanglei 2026"]),
        _note("Coordinate attack and counterbreak in the small center", "middlegame", "Before the Scheveningen f-pawn break, ensure the e-pawn remains defended and the dark squares around the king do not collapse. White should coordinate bishop, queen, and rook against e6 while preventing the central counterbreak that would release Black's position.", ["Scheveningen", "pawn break", "king safety"], 5, ["e6 target", "dark squares", "central counterbreak"], openings=["Sicilian Scheveningen"], games=["Wandor, Adam vs Iwan, Patryk 2026"]),
    ],
    "endgame.strategic.opposite_bishops": [
        _note("Attacking opposite bishops", "endgame", "With opposite-colored bishops, the side with the initiative should attack on the color complex the opponent cannot defend. Extra pawns or a safer king often matter more than exact material equality.", ["opposite-bishops", "color-complex", "initiative"], 2, ["opposite-bishops", "color-complex"]),
        _note("Drawing fortress ideas", "endgame", "The defender should place pawns on the color of their bishop, blockade passed pawns on the enemy bishop's color, and trade into a pure opposite-bishop ending when the attacker cannot create a second front.", ["fortress", "blockade", "draw-technique"], 3, ["opposite-bishops", "fortress"]),
        _note("Create two fronts", "middlegame", "To win opposite-bishop middlegames, combine kingside pressure with a queenside passer or a second weakness. One fixed target is often enough for a draw; two distant problems overwhelm the defending bishop.", ["two-weaknesses", "passed-pawn", "attack"], 4, ["opposite-bishops", "two-weaknesses"]),
    ],
}

def notes_for_key(key_id: str) -> list[dict]:
    return CANON_KEY_NOTES.get(key_id, [])
