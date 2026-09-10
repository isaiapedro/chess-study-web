from typing import Any

CANON_KEY_META: dict[str, dict[str, Any]] = {
    "attack.f7_f2_vulnerability": {
        "compact": "The f7 and f2 pawns are early tactical targets because only the king initially defends them. Fast development can turn pressure there into checks, forks, or mating threats.",
        "model_game": "Model game: Paul Morphy vs Karl Brunswick - 1858"
    },
    "attack.greek_gift": {
        "compact": "The Greek Gift is a bishop sacrifice on h7 or h2 that draws out the castled king for a queen-and-knight attack. It works only when the attackers have clear entry routes and the king lacks safe escapes.",
        "model_game": "Model game: Emanuel Lasker vs Johann Bauer - 1889"
    },
    "attack.initiative": {
        "compact": "The initiative is the ability to make threats that force the opponent to respond. It is sustained by moves that gain time while improving attacking coordination.",
        "model_game": "Model game: Garry Kasparov vs Veselin Topalov - 1999"
    },
    "attack.king_safety": {
        "compact": "King safety measures a king's exposure to open lines, weak squares, and coordinated attackers. Shelter, defenders, and escape squares matter more than castling alone.",
        "model_game": "Model game: Donald Byrne vs Robert Fischer - 1956"
    },
    "attack.opposite_side_castling": {
        "compact": "Opposite-side castling creates a race in which both players can advance pawns toward the enemy king. The faster side usually opens files first while keeping the center under control.",
        "model_game": "Model game: Anatoly Karpov vs Viktor Korchnoi - 1974"
    },
    "endgame.strategic.active_king": {
        "compact": "An active king enters the center or attacks weaknesses once mating danger has faded. Its activity can support passed pawns, restrict the enemy king, and decide simplified positions.",
        "model_game": "Model game: Jose Capablanca vs Savielly Tartakower - 1924"
    },
    "endgame.strategic.opposite_bishops": {
        "compact": "Opposite-colored bishops control different square complexes, often favoring the attacker with other pieces present but enabling fortresses in pure bishop endings. Winning chances usually require two distant targets.",
        "model_game": "Model game: Robert Fischer vs Tigran Petrosian - 1971"
    },
    "endgame.strategic.pawn_break": {
        "compact": "An endgame pawn break changes a fixed structure to create a passer, entry route, or permanent weakness. Its value comes from the resulting position rather than the exchanged pawn.",
        "model_game": "Model game: Jose Capablanca vs Savielly Tartakower - 1924"
    },
    "endgame.theoretical.fortress": {
        "compact": "A fortress is a defensive setup that cannot be breached despite a material disadvantage. Stable blockades, inaccessible entry squares, and the absence of useful pawn breaks are its main features.",
        "model_game": "Model game: Viktor Korchnoi vs Garry Kasparov - 1991"
    },
    "endgame.theoretical.lucena": {
        "compact": "The Lucena position is a winning rook-and-pawn ending with the stronger king in front of a seventh-rank pawn and the enemy king cut off. The winning method builds a rook bridge against side checks.",
        "model_game": "Model game: Anatoly Karpov vs Garry Kasparov - 1987"
    },
    "endgame.theoretical.philidor": {
        "compact": "The Philidor position is a drawing rook defense that bars the attacking king with third-rank control. After the pawn advances, the rook retreats and checks from behind.",
        "model_game": "Model game: Max Euwe vs Vasily Smyslov - 1947"
    },
    "endgame.theoretical.triangulation": {
        "compact": "Triangulation is a king maneuver that returns to the same square after losing a tempo. It transfers the move to the opponent and creates zugzwang.",
        "model_game": "Model game: Jose Capablanca vs Ilia Kan - 1936"
    },
    "endgame.theoretical.vancura": {
        "compact": "The Vancura defense draws against a rook pawn on the sixth rank by attacking it laterally and checking the king from the side. The defending rook preserves distance and stays active.",
        "model_game": "Model game: Josef Vancura vs Endre Steiner - 1924"
    },
    "imbalance.bishop_pair": {
        "compact": "The bishop pair is the advantage of retaining both bishops, especially in open positions with targets on both colors and wings. Pawn breaks increase its scope.",
        "model_game": "Model game: Mikhail Botvinnik vs Jose Capablanca - 1938"
    },
    "imbalance.good_vs_bad_bishop": {
        "compact": "A good bishop works outside its pawn chain and attacks useful targets, while a bad bishop is restricted by its own fixed pawns. Structural changes and exchanges can reverse those roles.",
        "model_game": "Model game: Anatoly Karpov vs Wolfgang Unzicker - 1974"
    },
    "imbalance.knight_vs_bishop": {
        "compact": "Knights favor closed positions and stable outposts, while bishops favor open lines and play on both wings. The future pawn structure determines which minor piece is superior.",
        "model_game": "Model game: Garry Kasparov vs Anatoly Karpov - 1985"
    },
    "imbalance.material_asymmetry": {
        "compact": "Material asymmetry compares unlike forces, such as a rook against minor pieces or material against initiative. Activity, king safety, structure, and durable targets determine the real balance.",
        "model_game": "Model game: Tigran Petrosian vs Boris Spassky - 1966"
    },
    "imbalance.space": {
        "compact": "A space advantage gives pieces more useful squares while restricting the opponent. It must be supported because advanced pawns can become targets and require timely breaks.",
        "model_game": "Model game: Aron Nimzowitsch vs Paul Johner - 1926"
    },
    "methodology.candidate_moves": {
        "compact": "Candidate moves are the small set of plausible choices selected before calculation. They should include forcing moves, defensive resources, and position-improving alternatives.",
        "model_game": "Model game: Alexander Alekhine vs Jose Capablanca - 1927"
    },
    "methodology.comparison_and_elimination": {
        "compact": "Comparison and elimination evaluates candidate moves by their resulting positions and removes those that fail tactically or strategically. It prevents choosing the first acceptable idea.",
        "model_game": "Model game: Garry Kasparov vs Anatoly Karpov - 1985"
    },
    "methodology.prophylactic_thinking": {
        "compact": "Prophylactic thinking identifies the opponent's intended plan before choosing a move. The best preventive moves also improve one's own position.",
        "model_game": "Model game: Anatoly Karpov vs Boris Spassky - 1974"
    },
    "methodology.visualization": {
        "compact": "Visualization is the ability to track the complete board accurately through an imagined sequence. It includes changed lines, removed defenders, and the exact final position.",
        "model_game": "Model game: Garry Kasparov vs Veselin Topalov - 1999"
    },
    "motif.discovered_attack": {
        "compact": "A discovered attack occurs when one piece moves and uncovers an attack by a rook, bishop, or queen behind it. The moving piece is strongest when it creates a second threat.",
        "model_game": "Model game: Paul Morphy vs Karl Brunswick - 1858"
    },
    "motif.intermediate_move": {
        "compact": "An intermediate move inserts a forcing action before an expected recapture or continuation. A check, capture, or threat can change the final outcome of the sequence.",
        "model_game": "Model game: Richard Reti vs Savielly Tartakower - 1910"
    },
    "motif.pin_and_skewer": {
        "compact": "A pin restrains a front piece because moving it exposes a more valuable target, while a skewer drives the valuable front piece away to win the piece behind it.",
        "model_game": "Model game: Samuel Reshevsky vs Vasily Smyslov - 1953"
    },
    "motif.trapped_piece": {
        "compact": "A trapped piece has no safe escape squares and will be lost once the opponent can attack it with tempo. Count flight squares before the capture appears.",
        "model_game": "Model game: Jose Capablanca vs Frank Marshall - 1909"
    },
    "motif.sacrifice": {
        "compact": "A sacrifice gives up material for concrete compensation such as exposed king safety, initiative, development, or a passed pawn. Its soundness depends on the resulting position.",
        "model_game": "Model game: Mikhail Tal vs Mikhail Botvinnik - 1960"
    },
    "opening.caro_kann": {
        "compact": "The Caro-Kann Defence answers e4 with a sound pawn structure and prepares a central challenge with d5. Black usually develops the light-squared bishop before e6 and later seeks c5 or e5.",
        "model_game": "Model game: Anatoly Karpov vs Gata Kamsky - 1996"
    },
    "opening.english": {
        "compact": "The English Opening begins with c4 and controls the center from the flank. Its flexible structures often feature a kingside fianchetto, queenside expansion, or a later d4 break.",
        "model_game": "Model game: Mikhail Botvinnik vs Milan Vidmar - 1936"
    },
    "opening.french": {
        "compact": "The French Defence builds a d5-e6 chain against White's e4 center. Black attacks the pawn-chain base with c5 and later challenges its head with f6.",
        "model_game": "Model game: Mikhail Botvinnik vs Jose Capablanca - 1938"
    },
    "opening.italian": {
        "compact": "The Italian Game develops the bishop to c4 and creates early central and kingside pressure. Quiet systems prepare d4 through patient development, while Black seeks an active d5 break.",
        "model_game": "Model game: Anatoly Karpov vs Viktor Korchnoi - 1981"
    },
    "opening.kings_indian": {
        "compact": "The King's Indian Defence concedes central space before attacking the center with e5 or c5. Closed structures commonly produce White's queenside expansion against Black's kingside attack.",
        "model_game": "Model game: Garry Kasparov vs Viktor Korchnoi - 1993"
    },
    "opening.london_system": {
        "compact": "The London System develops the dark-squared bishop before e3 and supports d4 with a compact setup. White later chooses between e4 expansion and kingside pressure.",
        "model_game": "Model game: Gata Kamsky vs Samuel Shankland - 2014"
    },
    "opening.petroff": {
        "compact": "The Petroff Defence meets e4 symmetrically with Nf6 and seeks rapid central equality. Accurate development and timely central play matter more than copying moves.",
        "model_game": "Model game: Vladimir Kramnik vs Viswanathan Anand - 2008"
    },
    "opening.queens_gambit": {
        "compact": "The Queen's Gambit uses c4 to challenge Black's d5 pawn and increase central influence. Its plans depend on whether the center becomes accepted, isolated, hanging, Slav, or Carlsbad.",
        "model_game": "Model game: Jose Capablanca vs Alexander Alekhine - 1927"
    },
    "opening.ruy_lopez": {
        "compact": "The Ruy Lopez develops the bishop to b5 and increases pressure on Black's e5 center. Closed lines reward deep maneuvering, while Black seeks queenside space and the freeing d5 break.",
        "model_game": "Model game: Anatoly Karpov vs Viktor Korchnoi - 1978"
    },
    "opening.scandinavian": {
        "compact": "The Scandinavian Defence challenges e4 immediately with d5 and accepts early queen exposure for a clear structure. Black must complete development and use c5 or e5 before lost tempi become serious.",
        "model_game": "Model game: Viswanathan Anand vs Joel Lautier - 1997"
    },
    "opening.sicilian": {
        "compact": "The Sicilian Defence answers e4 with c5 and creates an asymmetrical structure with active counterplay. White often attacks the king while Black uses the c-file, queenside expansion, and central breaks.",
        "model_game": "Model game: Garry Kasparov vs Veselin Topalov - 1999"
    },
    "piece.blockade": {
        "compact": "A blockade places a stable piece in front of a passed or isolated pawn to stop its advance. The blocked pawn can then become a fixed target.",
        "model_game": "Model game: Aron Nimzowitsch vs Friedrich Saemisch - 1923"
    },
    "piece.centralization": {
        "compact": "Centralization places a piece where it influences both wings and can change tasks quickly. A centralized piece should serve a concrete function and remain tactically stable.",
        "model_game": "Model game: Jose Capablanca vs Savielly Tartakower - 1924"
    },
    "piece.coordination": {
        "compact": "Piece coordination means that pieces support one another and perform complementary jobs toward the same plan. Coordinated forces can attack, defend, or escort a passer without losing key control.",
        "model_game": "Model game: Paul Morphy vs Karl Brunswick - 1858"
    },
    "piece.rerouting": {
        "compact": "Rerouting transfers a poorly placed piece along a safe path to a more useful square. The destination should support a break, attack a weakness, or restrict counterplay.",
        "model_game": "Model game: Anatoly Karpov vs Wolfgang Unzicker - 1974"
    },
    "piece.seventh_rank_invasion": {
        "compact": "A seventh-rank invasion places a rook where it attacks pawns laterally, restricts the king, and creates mating or promotion threats. Entry usually requires control of an open file.",
        "model_game": "Model game: Jose Capablanca vs Herman Steiner - 1933"
    },
    "piece.simplification": {
        "compact": "Simplification exchanges pieces to reduce counterplay or reach a favorable ending. The decision must preserve the useful pieces and the underlying advantage.",
        "model_game": "Model game: Jose Capablanca vs Savielly Tartakower - 1924"
    },
    "positional.color_complexes": {
        "compact": "A color complex is a connected group of squares of one color made weak by pawn placement or a missing bishop. Pieces can coordinate to occupy and attack those squares.",
        "model_game": "Model game: Robert Fischer vs Boris Spassky - 1972"
    },
    "positional.outpost": {
        "compact": "An outpost is a useful square that enemy pawns cannot safely challenge. A piece placed there should create threats, restrict play, or support a key break.",
        "model_game": "Model game: Anatoly Karpov vs Boris Spassky - 1974"
    },
    "positional.pawn_break": {
        "compact": "A pawn break is a pawn advance or exchange that deliberately changes the structure. It should open a line, undermine a chain, create a passer, or secure a useful square.",
        "model_game": "Model game: Mikhail Botvinnik vs Jose Capablanca - 1938"
    },
    "positional.prophylaxis": {
        "compact": "Prophylaxis prevents an opponent's plan before it becomes a direct threat. It commonly restrains a freeing break or denies a key regrouping square.",
        "model_game": "Model game: Anatoly Karpov vs Boris Spassky - 1974"
    },
    "positional.restriction": {
        "compact": "Restriction limits the opponent's useful moves, squares, and pawn breaks before an advantage is converted. It creates time for calm piece improvement.",
        "model_game": "Model game: Aron Nimzowitsch vs Paul Johner - 1926"
    },
    "positional.two_weaknesses": {
        "compact": "The principle of two weaknesses stretches a defender by creating distant targets that cannot both be protected efficiently. The first weakness is fixed before play switches to the second.",
        "model_game": "Model game: Jose Capablanca vs Savielly Tartakower - 1924"
    },
    "structure.carlsbad": {
        "compact": "The Carlsbad structure has opposing c- and e-pawns around a fixed d-pawn center. Typical plans include a queenside minority attack, central expansion, and a kingside initiative.",
        "model_game": "Model game: Jose Capablanca vs Alexander Alekhine - 1927"
    },
    "structure.caro_slav": {
        "compact": "The Caro-Slav structure features a sound c6-d5 base and a light-squared bishop often developed outside the chain. Play centers on challenging an advanced pawn and timing c5 or e5.",
        "model_game": "Model game: Anatoly Karpov vs Gata Kamsky - 1996"
    },
    "structure.doubled_pawns": {
        "compact": "Doubled pawns share a file and may become fixed targets because they cannot protect each other normally. They can still provide open files, square control, and useful restraint.",
        "model_game": "Model game: Robert Fischer vs Boris Spassky - 1972"
    },
    "structure.dragon_formation": {
        "compact": "The Dragon formation combines a kingside fianchetto with a pawn structure that activates the bishop along the long diagonal. Its dynamic potential depends on central and queenside counterbreaks.",
        "model_game": "Model game: Anatoly Karpov vs Viktor Korchnoi - 1974"
    },
    "structure.hanging_pawns": {
        "compact": "Hanging pawns are adjacent isolated pawns, usually on c4 and d4 or their counterparts. They grant space and dynamic breaks but become weaknesses if fixed or blockaded.",
        "model_game": "Model game: Garry Kasparov vs Anatoly Karpov - 1985"
    },
    "structure.hedgehog": {
        "compact": "The Hedgehog is a compact setup that accepts less space while preparing sudden b5 or d5 breaks. Its pieces store energy behind a restrained pawn shell.",
        "model_game": "Model game: Ulf Andersson vs Anatoly Karpov - 1975"
    },
    "structure.iqp": {
        "compact": "An isolated queen pawn grants space, open lines, and active piece play but lacks neighboring pawn support. Its owner seeks activity or a liberating advance before simplification.",
        "model_game": "Model game: Garry Kasparov vs Anatoly Karpov - 1985"
    },
    "structure.maroczy_bind": {
        "compact": "The Maroczy Bind uses pawns on c4 and e4 to restrict central freeing breaks, especially d5. The space advantage requires patient improvement without loosening control.",
        "model_game": "Model game: Geza Maroczy vs Max Euwe - 1921"
    },
    "structure.passed_pawn": {
        "compact": "A passed pawn has no opposing pawn able to stop it on its file or adjacent files. It gains value by advancing, tying down a blockader, and receiving coordinated support.",
        "model_game": "Model game: Jose Capablanca vs Savielly Tartakower - 1924"
    },
    "structure.pawn_chain": {
        "compact": "A pawn chain is a diagonal group of mutually supporting pawns whose base and head determine breaks and piece routes. It is usually attacked at its support or undermined at its front.",
        "model_game": "Model game: Mikhail Botvinnik vs Jose Capablanca - 1938"
    },
    "structure.scheveningen": {
        "compact": "The Scheveningen structure uses Black pawns on e6 and d6 to form a compact, flexible center. Black seeks central counterbreaks while White uses space for a kingside attack.",
        "model_game": "Model game: Garry Kasparov vs Leonid Ljubojevic - 1987"
    }
}

NOTE_COMPACT_BY_KEY: dict[str, list[str]] = {
  "attack.f7_f2_vulnerability": [
    "Before launching an attack, check whether f7 or f2 is defended only by the king.",
    "Pressure on f7 or f2 becomes dangerous when a bishop attacks along the diagonal and a queen or knight can…",
    "When a check drives the king onto the f-file, look for a second check that captures on f7 or f2 and exposes…",
    "A threat against f7 or f2 can be useful even when it does not win immediately."
  ],
  "attack.greek_gift": [
    "The Greek Gift is a bishop sacrifice on h7 or h2 designed to drag the castled king out and bring the queen…",
    "Before sacrificing on h7, verify that the knight can reach g5 with tempo, the queen can enter on h5 or the…",
    "The sacrifice is stronger when the defender on f6 is absent, pinned, or unable to control h7 and g4, while…",
    "After the king accepts the Greek Gift, calculate forcing moves in order: knight checks, queen checks, and…"
  ],
  "attack.initiative": [
    "The initiative belongs to the side making threats that demand answers.",
    "An initiative can survive a queen trade when active rooks, advanced pawns, or exposed pieces continue to…",
    "When both kings are vulnerable, the player who attacks first often becomes safer because the opponent's…",
    "An advanced pawn can maintain the initiative by attacking a rook's squares while a knight threatens a fork…"
  ],
  "attack.king_safety": [
    "King safety is determined by open lines, available defenders, and flight squares more than by whether the…",
    "A pawn storm is effective when it opens files for heavy pieces without exposing your own king first.",
    "When attacking a castled king, identify the key defender before calculating sacrifices.",
    "A kingside pawn advance can compensate for queenside weaknesses only if it creates immediate entry squares…"
  ],
  "attack.opposite_side_castling": [
    "With opposite-side castling, speed usually matters more than pawn weaknesses because each side can advance…",
    "In many Sicilian Defense structures with opposite-side castling, White attacks with kingside pawns while…",
    "A queenside pawn thrust that drives a knight from c3 can gain a crucial attacking tempo and reduce control…",
    "Do not attack on autopilot when the center can open."
  ],
  "endgame.strategic.active_king": [
    "In simplified positions, the king becomes a fighting piece.",
    "A better king can turn an otherwise equal pawn structure into a lasting advantage.",
    "In a rook ending, a king route to d5 or e5 can matter more than an immediate pawn push."
  ],
  "endgame.strategic.pawn_break": [
    "Do not treat every endgame pawn move as a race toward promotion.",
    "Look for an advanced enemy pawn that acts as a hook.",
    "Before playing a break such as f5-f4 in a rook ending, check whether it drives the defending rook away from…"
  ],
  "endgame.theoretical.fortress": [
    "A material advantage does not guarantee a win when the defender can build a fortress.",
    "Opposite-colored bishop endings often become fortresses because the defender can control the promotion color…",
    "Against a bishop-and-rook-pawn fortress, first verify whether the bishop controls the pawn's promotion square."
  ],
  "endgame.theoretical.lucena": [
    "In winning rook endings, place the rook where it can shield the king from checks while the king escorts the…",
    "The Lucena method applies when the stronger king stands in front of a pawn on the seventh rank and the enemy…",
    "In the Lucena position, build the bridge by placing the rook on the fourth rank, stepping the king out under…"
  ],
  "endgame.theoretical.philidor": [
    "The defender in a rook ending should keep the attacking king away from the promotion zone and preserve…",
    "The Philidor defense holds when the pawn has not passed the fifth rank: keep the rook on the third rank to…",
    "In the central-pawn Philidor setup, do not abandon the third rank while the attacking king is still blocked."
  ],
  "endgame.theoretical.triangulation": [
    "Triangulation is a controlled loss of tempo: the king uses three moves to return to the same square while…",
    "Count reserve pawn tempi before triangulating.",
    "In king-and-pawn endings, triangulate only when the returning king move hands the opponent the same position…"
  ],
  "endgame.theoretical.vancura": [
    "A rook can often draw against a rook pawn by attacking it from the side while the king remains near the…",
    "The Vancura defense works against a rook pawn on the sixth rank when the stronger rook protects it from…",
    "In the Vancura position, place the rook far enough along the fourth rank to attack the pawn laterally…"
  ],
  "imbalance.bishop_pair": [
    "The bishop pair matters most in open positions with targets on both colors.",
    "With the bishop pair, use pawn breaks to remove central blockades and create play on both wings.",
    "In an endgame with bishops against a knight and bishop, an outside pawn majority increases the power of the…"
  ],
  "imbalance.good_vs_bad_bishop": [
    "A bishop is bad when its own fixed pawns block its diagonals or create targets on its color.",
    "Against a bad bishop, fix enemy pawns on that bishop's color and occupy the opposite color with your king or…",
    "In a French-style locked center, a bishop trapped behind the pawn chain can remain strategically inferior to…"
  ],
  "imbalance.knight_vs_bishop": [
    "Knights thrive in closed positions with stable outposts; bishops thrive in open positions and across both…",
    "A bishop usually gains value when play occurs on both wings or an outside passed pawn appears.",
    "In a bishop-versus-knight ending with an outside majority and the more active king, open a second wing…"
  ],
  "imbalance.material_asymmetry": [
    "Unequal material must be evaluated by function, not points alone.",
    "When you have the material advantage, exchange the opponent's most active pieces and preserve the pawns that…",
    "An exchange sacrifice is justified when the minor piece gains a stable blockade, key-square control, and…"
  ],
  "imbalance.space": [
    "A space advantage gives your pieces more useful squares and restricts the opponent, but it also creates…",
    "With more space, avoid releasing central tension without a reason.",
    "With a pawn chain led by a pawn on d5, a c-pawn lever often expands on the chain's pointed side and opens…"
  ],
  "methodology.candidate_moves": [
    "Before calculating, list a small set of moves that answer the position's most urgent need: checks, captures,…",
    "Compare forcing moves with quiet alternatives.",
    "When one pawn is attacked and another can be captured, include defending, counterattacking, and changing the…"
  ],
  "methodology.comparison_and_elimination": [
    "Do not choose the first acceptable move.",
    "Use a familiar pawn structure as a reference, but identify what changed: piece placement, available breaks,…",
    "When comparing an attack with a positional regrouping, ask whether the pawn storm is still risk-free,…"
  ],
  "methodology.prophylactic_thinking": [
    "Before every serious decision, ask what the opponent wants next and which of their pieces or pawn breaks…",
    "Prefer a useful move that both improves your position and hinders the opponent.",
    "If the opponent needs a queen retreat or regrouping square to free cramped pieces, control that square first."
  ],
  "methodology.visualization": [
    "Visualize the final position, not merely the move sequence.",
    "Train board vision by naming square colors and coordinates, then reconstructing piece placement from memory.",
    "In a closed center, visualize candidate pawn breaks through the resulting files and diagonals."
  ],
  "motif.discovered_attack": [
    "A discovered attack occurs when one piece moves away and uncovers an attack by a piece behind it.",
    "The strongest discoveries make the moving piece create a second threat, especially check.",
    "When a queen and king or queen and rook lie on the same line, look for a check by the blocking piece that…",
    "A bishop sacrifice on h2 or h7 can function as a discovery when accepting it opens a queen or rook attack on…"
  ],
  "motif.intermediate_move": [
    "Before making an expected recapture, check whether a forcing move can be inserted first.",
    "An intermediate check is especially powerful because the opponent must respond before restoring material…",
    "When a piece is expected to recapture in the center, a rook check on an open file can force the king to an…",
    "A quiet intermediate threat can be stronger than a check when it traps a piece or attacks a more valuable…"
  ],
  "motif.pin_and_skewer": [
    "A pin restrains the front piece because moving it exposes something more valuable; a skewer forces the…",
    "Absolute pins against the king often allow the pinned piece to be captured or attacked again because it…",
    "A rook check along a rank can skewer an exposed king to an undefended rook or queen behind it.",
    "A rook on an open file can pin a bishop or knight to the king, then capture the pinned piece after the…"
  ],
  "motif.sacrifice": [
    "A sacrifice exchanges material for concrete compensation such as king exposure, rapid development, a passed…",
    "For an attacking sacrifice, calculate checks, captures, and threats until the defender reaches a stable…",
    "A pawn sacrifice can open a file, clear an entry square, or distract a defender from the main wing.",
    "In a rook ending, sacrificing the rook for a dangerous passed pawn can be correct when the remaining pawns…"
  ],
  "opening.caro_kann": [
    "The Caro-Kann Defence gives Black a sound pawn structure and usually a safe king.",
    "In the Caro-Kann, Black should solve the light-squared bishop before locking the center with ...e6 whenever…",
    "Against the Caro-Kann Advance structure, Black attacks the base and head of White's e5-d4 chain with ...c5…",
    "In Caro-Kann endgames, Black's structural health matters only if the pieces become active."
  ],
  "opening.english": [
    "The English Opening controls the center from the flank and often delays a direct pawn occupation.",
    "English Opening positions often transpose, so plans matter more than labels.",
    "In Symmetrical English structures, an early d4 break can open files before Black is fully coordinated, while…",
    "In Botvinnik-style English structures with pawns on c4 and e4, White gains space but weakens d4."
  ],
  "opening.french": [
    "The French Defence creates a locked or semi-locked center in which each side attacks a pawn chain.",
    "French Defence strategy revolves around Black's light-squared bishop and timely pawn breaks.",
    "In the French Advance, White can support a kingside attack with f4-f5, queen pressure on h5, and rook lifts…",
    "When the French center transforms into an isolated d-pawn position, blockading d5 is not automatically enough."
  ],
  "opening.italian": [
    "The Italian Game develops rapidly toward the center and kingside.",
    "Quiet Italian positions reward patient maneuvering.",
    "In Italian middlegames with tension on d4, White often keeps pieces on the board and aims them at Black's…",
    "In Italian positions where White gains a queenside pawn, conversion depends on restraining counterplay…"
  ],
  "opening.kings_indian": [
    "The King's Indian Defence concedes central space so Black can attack it later.",
    "In closed King's Indian structures, the pawn chains point toward opposite wings.",
    "Black's thematic ...f5 break in the King's Indian attacks e4 and can open the f-file.",
    "King's Indian endgames can reverse the opening's attacking logic: once queens are gone, Black's king and…"
  ],
  "opening.london_system": [
    "The London System builds a reliable dark-square setup with the bishop developed before e3.",
    "The London System is not only a fixed setup: White must react to Black's structure.",
    "In London middlegames, a knight on e5 supports direct play with Bd3, Qf3 or Qh5, and a kingside pawn advance.",
    "When Black plays an early ...Bf5 against the London System, White can challenge that bishop and use Qb3 to…"
  ],
  "opening.petroff": [
    "The Petroff Defence meets White's central play symmetrically and aims for rapid development rather than…",
    "Petroff positions often simplify into balanced middlegames, so small improvements matter.",
    "When White keeps the king in the center in a sharp Petroff branch, Black can use active bishop development…",
    "Against Petroff move-order sidelines, Black should preserve the defence's character without forcing a…"
  ],
  "opening.queens_gambit": [
    "The Queen's Gambit family uses the c-pawn to challenge Black's d5-pawn and build central influence.",
    "Queen's Gambit middlegames are defined by structure.",
    "In the Queen's Gambit Exchange Variation, White's minority attack with b4-b5 tries to create a fixed…",
    "In Queen's Gambit Accepted structures, Black usually returns the c4-pawn rather than spending time trying to…"
  ],
  "opening.ruy_lopez": [
    "The Ruy Lopez increases pressure on Black's e5-pawn while preserving flexible central play.",
    "Closed Ruy Lopez positions reward long maneuvers because the center restricts immediate tactics.",
    "In the Exchange Ruy Lopez, White can accept the bishop pair to damage Black's queenside pawns and aim for a…",
    "In Marshall-style Ruy Lopez positions, Black sacrifices a pawn to accelerate development and attack the…"
  ],
  "opening.scandinavian": [
    "The Scandinavian Defence challenges White's e4-pawn immediately and forces an early central exchange.",
    "Scandinavian structures often resemble the Caro-Kann or Slav: Black develops the light-squared bishop before…",
    "In ...Qd6 Scandinavian setups, Black's queen supports e5 and kingside castling but can obstruct the…",
    "Scandinavian endgames can favor Black when the opening's early exchange leaves a sound, easy-to-defend…"
  ],
  "opening.sicilian": [
    "The Sicilian Defence creates an asymmetrical fight: Black exchanges the c-pawn for White's d-pawn and gains…",
    "Open Sicilian middlegames often feature opposite-wing attacks.",
    "In Najdorf English Attack structures, White often castles queenside and advances f3, g4, and h4, while Black…",
    "Against a Maroczy Bind, Black has less space but can build a Hedgehog with pawns on a6, b6, d6, and e6."
  ],
  "piece.blockade": [
    "A blockade stops a passed or isolated pawn and turns it into a target.",
    "Knights are often ideal blockaders because they can attack while occupying the square in front of the pawn.",
    "Against connected or doubled passers, establish the blockade before they advance with tempo."
  ],
  "piece.centralization": [
    "Centralized pieces influence both wings and can switch tasks quickly.",
    "Centralization is valuable when it supports a pawn break, attacks a weakness, or escorts a passer.",
    "In a rook-and-pawn ending, place the king diagonally ahead of the passer when possible, support the pawn…"
  ],
  "piece.coordination": [
    "Pieces are coordinated when they support the same plan, cover one another, and can change roles without…",
    "A passed pawn becomes dangerous when pieces escort it while controlling blockade squares.",
    "Before pushing connected passers, assign each piece a task: one controls the blockading square, one covers…"
  ],
  "piece.rerouting": [
    "When a piece has no useful targets, reroute it toward a stable square that supports the position's main…",
    "In symmetrical structures, patient rerouting is often stronger than creating unnecessary pawn weaknesses.",
    "A knight stranded on the flank or tied to a pawn can often return through the back rank to a central support…"
  ],
  "piece.seventh_rank_invasion": [
    "A rook on the seventh rank attacks pawns from the side, restricts the king, and often creates mating or…",
    "An invasion is strongest when another piece controls the escape squares or a passed pawn distracts the…",
    "In a rook ending, combine a seventh-rank rook with an advancing king that attacks the defender's pawns."
  ],
  "piece.simplification": [
    "Simplify when exchanges preserve your advantage and remove the opponent's active resources.",
    "Trade your bad minor piece for the opponent's good one, or exchange attackers when defending.",
    "Before entering a pawn ending, verify king access, reserve tempi, and pawn breaks."
  ],
  "positional.color_complexes": [
    "Pawn moves permanently weaken squares of one color.",
    "Judge a color complex through the pawn structure and bishop placement, not the exact position alone.",
    "When kingside pawns are fixed on dark squares and the dark-squared bishop is absent, build a…"
  ],
  "positional.outpost": [
    "An outpost is a useful square that cannot be challenged safely by an enemy pawn.",
    "Pawn structure determines outposts.",
    "Before installing a knight on a central outpost, prevent the pawn break that would undermine its support and…"
  ],
  "positional.pawn_break": [
    "A pawn break should open a line, challenge a chain, create a passer, or gain a useful square.",
    "Identify whether to attack the head or base of the pawn chain.",
    "With hanging pawns, time the central advance while both pawns are defended and your pieces can use the…"
  ],
  "positional.prophylaxis": [
    "Prophylaxis means preventing the opponent's plan before it becomes a direct threat.",
    "In a familiar structure, identify the lever that releases the opponent's cramped pieces.",
    "Against an IQP, prevent the liberating advance before piling up on the pawn."
  ],
  "positional.restriction": [
    "Restriction reduces the opponent's useful moves before you attack.",
    "A spatial advantage matters when the pawn structure denies good squares to enemy pieces.",
    "If control of e5 dominates the position, reinforce that square, neutralize the defender that contests it,…"
  ],
  "positional.two_weaknesses": [
    "One weakness can often be defended.",
    "Fix the first target before switching wings.",
    "When a kingside pawn is already weak, provoke a queenside pawn into becoming a second target."
  ],
  "structure.carlsbad": [
    "In the Carlsbad structure, plans come from the fixed central pawn skeleton: a queenside minority attack,…",
    "The minority attack uses fewer queenside pawns to provoke a backward or isolated pawn.",
    "Before the Carlsbad b-pawn break, place rooks on the files likely to open and ensure a knight can occupy the…"
  ],
  "structure.caro_slav": [
    "The Caro-Slav family is defined by one side's advanced d-pawn against a restrained opposing center.",
    "In Caro-Slav structures, compare breaks against the front of the chain with breaks against its base.",
    "If an advanced e-pawn merely blocks your bishop and rook, returning or sacrificing it can restore…"
  ],
  "structure.doubled_pawns": [
    "Doubled pawns are weaknesses only when they can be attacked or cannot create useful control.",
    "In an ending, fix doubled pawns before attacking them.",
    "Do not repair doubled kingside pawns automatically if they still halt an enemy majority and remain easy for…"
  ],
  "structure.dragon_formation": [
    "The Dragon formation features a kingside fianchetto aimed at a center that may open.",
    "Dragon positions should be recognized by structure even with colors reversed.",
    "Against a Maróczy-style bind, the Dragon bishop needs a pawn break to become active."
  ],
  "structure.hanging_pawns": [
    "Hanging pawns offer space and dynamic breaks but can become fixed targets.",
    "The side with hanging pawns should prepare a central advance or kingside activity.",
    "Before simplifying a hanging-pawn position, check whether exchanges remove the pieces that support the…"
  ],
  "structure.hedgehog": [
    "The Hedgehog accepts less space in return for a compact pawn shell and prepared counterbreaks.",
    "The Hedgehog player seeks freeing central or queenside breaks; the space-advantaged side restrains them and…",
    "In a Hedgehog, place rooks and queen behind the central breaks and reroute a knight toward active kingside…"
  ],
  "structure.iqp": [
    "An IQP grants space, open lines, and active piece play, but becomes a long-term target if its advance is…",
    "The IQP side should coordinate pieces for the liberating advance or a kingside attack.",
    "Before advancing an IQP, unpin the supporting knight and prevent the opponent's favorable bishop development…"
  ],
  "structure.maroczy_bind": [
    "The Maróczy Bind uses central pawns to restrict freeing breaks and limit opposing pieces.",
    "The cramped side seeks timely pawn breaks and piece exchanges; the side with the Maróczy Bind controls those…",
    "A knight reroute toward a stable queenside or central square can reinforce the Maróczy Bind while freeing…"
  ],
  "structure.passed_pawn": [
    "A passed pawn is valuable because it demands a blockade and ties down pieces.",
    "Create a passed pawn by fixing the opposing majority, opening the correct file, or forcing a favorable…",
    "Against a passed pawn, establish the blockade with the king or bishop before attacking its base."
  ],
  "structure.pawn_chain": [
    "In a locked center, pawn chains determine space, breaks, and piece routes.",
    "A closed center gives time to reroute pieces toward the wing where the chain points.",
    "When one lever attacks the front pawn and another attacks the base, compare which exchange opens the useful…"
  ],
  "structure.scheveningen": [
    "The Scheveningen small center is flexible but compact.",
    "Recognize the Scheveningen by the central pawn structure, whether reached from the Najdorf, Kan, or Taimanov.",
    "Before the Scheveningen f-pawn break, ensure the e-pawn remains defended and the dark squares around the…"
  ],
  "endgame.strategic.opposite_bishops": [
    "With opposite-colored bishops, the side with the initiative should attack on the color complex the opponent…",
    "The defender should place pawns on the color of their bishop, blockade passed pawns on the enemy bishop's…",
    "To win opposite-bishop middlegames, combine kingside pressure with a queenside passer or a second weakness."
  ]
}

NOTE_COMPACT: dict[str, str] = {
  "attack.f7_f2_vulnerability#0": "Before launching an attack, check whether f7 or f2 is defended only by the king.",
  "attack.f7_f2_vulnerability#1": "Pressure on f7 or f2 becomes dangerous when a bishop attacks along the diagonal and a queen or knight can…",
  "attack.f7_f2_vulnerability#2": "When a check drives the king onto the f-file, look for a second check that captures on f7 or f2 and exposes…",
  "attack.f7_f2_vulnerability#3": "A threat against f7 or f2 can be useful even when it does not win immediately.",
  "attack.greek_gift#0": "The Greek Gift is a bishop sacrifice on h7 or h2 designed to drag the castled king out and bring the queen…",
  "attack.greek_gift#1": "Before sacrificing on h7, verify that the knight can reach g5 with tempo, the queen can enter on h5 or the…",
  "attack.greek_gift#2": "The sacrifice is stronger when the defender on f6 is absent, pinned, or unable to control h7 and g4, while…",
  "attack.greek_gift#3": "After the king accepts the Greek Gift, calculate forcing moves in order: knight checks, queen checks, and…",
  "attack.initiative#0": "The initiative belongs to the side making threats that demand answers.",
  "attack.initiative#1": "An initiative can survive a queen trade when active rooks, advanced pawns, or exposed pieces continue to…",
  "attack.initiative#2": "When both kings are vulnerable, the player who attacks first often becomes safer because the opponent's…",
  "attack.initiative#3": "An advanced pawn can maintain the initiative by attacking a rook's squares while a knight threatens a fork…",
  "attack.king_safety#0": "King safety is determined by open lines, available defenders, and flight squares more than by whether the…",
  "attack.king_safety#1": "A pawn storm is effective when it opens files for heavy pieces without exposing your own king first.",
  "attack.king_safety#2": "When attacking a castled king, identify the key defender before calculating sacrifices.",
  "attack.king_safety#3": "A kingside pawn advance can compensate for queenside weaknesses only if it creates immediate entry squares…",
  "attack.opposite_side_castling#0": "With opposite-side castling, speed usually matters more than pawn weaknesses because each side can advance…",
  "attack.opposite_side_castling#1": "In many Sicilian Defense structures with opposite-side castling, White attacks with kingside pawns while…",
  "attack.opposite_side_castling#2": "A queenside pawn thrust that drives a knight from c3 can gain a crucial attacking tempo and reduce control…",
  "attack.opposite_side_castling#3": "Do not attack on autopilot when the center can open.",
  "endgame.strategic.active_king#0": "In simplified positions, the king becomes a fighting piece.",
  "endgame.strategic.active_king#1": "A better king can turn an otherwise equal pawn structure into a lasting advantage.",
  "endgame.strategic.active_king#2": "In a rook ending, a king route to d5 or e5 can matter more than an immediate pawn push.",
  "endgame.strategic.pawn_break#0": "Do not treat every endgame pawn move as a race toward promotion.",
  "endgame.strategic.pawn_break#1": "Look for an advanced enemy pawn that acts as a hook.",
  "endgame.strategic.pawn_break#2": "Before playing a break such as f5-f4 in a rook ending, check whether it drives the defending rook away from…",
  "endgame.theoretical.fortress#0": "A material advantage does not guarantee a win when the defender can build a fortress.",
  "endgame.theoretical.fortress#1": "Opposite-colored bishop endings often become fortresses because the defender can control the promotion color…",
  "endgame.theoretical.fortress#2": "Against a bishop-and-rook-pawn fortress, first verify whether the bishop controls the pawn's promotion square.",
  "endgame.theoretical.lucena#0": "In winning rook endings, place the rook where it can shield the king from checks while the king escorts the…",
  "endgame.theoretical.lucena#1": "The Lucena method applies when the stronger king stands in front of a pawn on the seventh rank and the enemy…",
  "endgame.theoretical.lucena#2": "In the Lucena position, build the bridge by placing the rook on the fourth rank, stepping the king out under…",
  "endgame.theoretical.philidor#0": "The defender in a rook ending should keep the attacking king away from the promotion zone and preserve…",
  "endgame.theoretical.philidor#1": "The Philidor defense holds when the pawn has not passed the fifth rank: keep the rook on the third rank to…",
  "endgame.theoretical.philidor#2": "In the central-pawn Philidor setup, do not abandon the third rank while the attacking king is still blocked.",
  "endgame.theoretical.triangulation#0": "Triangulation is a controlled loss of tempo: the king uses three moves to return to the same square while…",
  "endgame.theoretical.triangulation#1": "Count reserve pawn tempi before triangulating.",
  "endgame.theoretical.triangulation#2": "In king-and-pawn endings, triangulate only when the returning king move hands the opponent the same position…",
  "endgame.theoretical.vancura#0": "A rook can often draw against a rook pawn by attacking it from the side while the king remains near the…",
  "endgame.theoretical.vancura#1": "The Vancura defense works against a rook pawn on the sixth rank when the stronger rook protects it from…",
  "endgame.theoretical.vancura#2": "In the Vancura position, place the rook far enough along the fourth rank to attack the pawn laterally…",
  "imbalance.bishop_pair#0": "The bishop pair matters most in open positions with targets on both colors.",
  "imbalance.bishop_pair#1": "With the bishop pair, use pawn breaks to remove central blockades and create play on both wings.",
  "imbalance.bishop_pair#2": "In an endgame with bishops against a knight and bishop, an outside pawn majority increases the power of the…",
  "imbalance.good_vs_bad_bishop#0": "A bishop is bad when its own fixed pawns block its diagonals or create targets on its color.",
  "imbalance.good_vs_bad_bishop#1": "Against a bad bishop, fix enemy pawns on that bishop's color and occupy the opposite color with your king or…",
  "imbalance.good_vs_bad_bishop#2": "In a French-style locked center, a bishop trapped behind the pawn chain can remain strategically inferior to…",
  "imbalance.knight_vs_bishop#0": "Knights thrive in closed positions with stable outposts; bishops thrive in open positions and across both…",
  "imbalance.knight_vs_bishop#1": "A bishop usually gains value when play occurs on both wings or an outside passed pawn appears.",
  "imbalance.knight_vs_bishop#2": "In a bishop-versus-knight ending with an outside majority and the more active king, open a second wing…",
  "imbalance.material_asymmetry#0": "Unequal material must be evaluated by function, not points alone.",
  "imbalance.material_asymmetry#1": "When you have the material advantage, exchange the opponent's most active pieces and preserve the pawns that…",
  "imbalance.material_asymmetry#2": "An exchange sacrifice is justified when the minor piece gains a stable blockade, key-square control, and…",
  "imbalance.space#0": "A space advantage gives your pieces more useful squares and restricts the opponent, but it also creates…",
  "imbalance.space#1": "With more space, avoid releasing central tension without a reason.",
  "imbalance.space#2": "With a pawn chain led by a pawn on d5, a c-pawn lever often expands on the chain's pointed side and opens…",
  "methodology.candidate_moves#0": "Before calculating, list a small set of moves that answer the position's most urgent need: checks, captures,…",
  "methodology.candidate_moves#1": "Compare forcing moves with quiet alternatives.",
  "methodology.candidate_moves#2": "When one pawn is attacked and another can be captured, include defending, counterattacking, and changing the…",
  "methodology.comparison_and_elimination#0": "Do not choose the first acceptable move.",
  "methodology.comparison_and_elimination#1": "Use a familiar pawn structure as a reference, but identify what changed: piece placement, available breaks,…",
  "methodology.comparison_and_elimination#2": "When comparing an attack with a positional regrouping, ask whether the pawn storm is still risk-free,…",
  "methodology.prophylactic_thinking#0": "Before every serious decision, ask what the opponent wants next and which of their pieces or pawn breaks…",
  "methodology.prophylactic_thinking#1": "Prefer a useful move that both improves your position and hinders the opponent.",
  "methodology.prophylactic_thinking#2": "If the opponent needs a queen retreat or regrouping square to free cramped pieces, control that square first.",
  "methodology.visualization#0": "Visualize the final position, not merely the move sequence.",
  "methodology.visualization#1": "Train board vision by naming square colors and coordinates, then reconstructing piece placement from memory.",
  "methodology.visualization#2": "In a closed center, visualize candidate pawn breaks through the resulting files and diagonals.",
  "motif.discovered_attack#0": "A discovered attack occurs when one piece moves away and uncovers an attack by a piece behind it.",
  "motif.discovered_attack#1": "The strongest discoveries make the moving piece create a second threat, especially check.",
  "motif.discovered_attack#2": "When a queen and king or queen and rook lie on the same line, look for a check by the blocking piece that…",
  "motif.discovered_attack#3": "A bishop sacrifice on h2 or h7 can function as a discovery when accepting it opens a queen or rook attack on…",
  "motif.intermediate_move#0": "Before making an expected recapture, check whether a forcing move can be inserted first.",
  "motif.intermediate_move#1": "An intermediate check is especially powerful because the opponent must respond before restoring material…",
  "motif.intermediate_move#2": "When a piece is expected to recapture in the center, a rook check on an open file can force the king to an…",
  "motif.intermediate_move#3": "A quiet intermediate threat can be stronger than a check when it traps a piece or attacks a more valuable…",
  "motif.pin_and_skewer#0": "A pin restrains the front piece because moving it exposes something more valuable; a skewer forces the…",
  "motif.pin_and_skewer#1": "Absolute pins against the king often allow the pinned piece to be captured or attacked again because it…",
  "motif.pin_and_skewer#2": "A rook check along a rank can skewer an exposed king to an undefended rook or queen behind it.",
  "motif.pin_and_skewer#3": "A rook on an open file can pin a bishop or knight to the king, then capture the pinned piece after the…",
  "motif.sacrifice#0": "A sacrifice exchanges material for concrete compensation such as king exposure, rapid development, a passed…",
  "motif.sacrifice#1": "For an attacking sacrifice, calculate checks, captures, and threats until the defender reaches a stable…",
  "motif.sacrifice#2": "A pawn sacrifice can open a file, clear an entry square, or distract a defender from the main wing.",
  "motif.sacrifice#3": "In a rook ending, sacrificing the rook for a dangerous passed pawn can be correct when the remaining pawns…",
  "opening.caro_kann#0": "The Caro-Kann Defence gives Black a sound pawn structure and usually a safe king.",
  "opening.caro_kann#1": "In the Caro-Kann, Black should solve the light-squared bishop before locking the center with ...e6 whenever…",
  "opening.caro_kann#2": "Against the Caro-Kann Advance structure, Black attacks the base and head of White's e5-d4 chain with ...c5…",
  "opening.caro_kann#3": "In Caro-Kann endgames, Black's structural health matters only if the pieces become active.",
  "opening.english#0": "The English Opening controls the center from the flank and often delays a direct pawn occupation.",
  "opening.english#1": "English Opening positions often transpose, so plans matter more than labels.",
  "opening.english#2": "In Symmetrical English structures, an early d4 break can open files before Black is fully coordinated, while…",
  "opening.english#3": "In Botvinnik-style English structures with pawns on c4 and e4, White gains space but weakens d4.",
  "opening.french#0": "The French Defence creates a locked or semi-locked center in which each side attacks a pawn chain.",
  "opening.french#1": "French Defence strategy revolves around Black's light-squared bishop and timely pawn breaks.",
  "opening.french#2": "In the French Advance, White can support a kingside attack with f4-f5, queen pressure on h5, and rook lifts…",
  "opening.french#3": "When the French center transforms into an isolated d-pawn position, blockading d5 is not automatically enough.",
  "opening.italian#0": "The Italian Game develops rapidly toward the center and kingside.",
  "opening.italian#1": "Quiet Italian positions reward patient maneuvering.",
  "opening.italian#2": "In Italian middlegames with tension on d4, White often keeps pieces on the board and aims them at Black's…",
  "opening.italian#3": "In Italian positions where White gains a queenside pawn, conversion depends on restraining counterplay…",
  "opening.kings_indian#0": "The King's Indian Defence concedes central space so Black can attack it later.",
  "opening.kings_indian#1": "In closed King's Indian structures, the pawn chains point toward opposite wings.",
  "opening.kings_indian#2": "Black's thematic ...f5 break in the King's Indian attacks e4 and can open the f-file.",
  "opening.kings_indian#3": "King's Indian endgames can reverse the opening's attacking logic: once queens are gone, Black's king and…",
  "opening.london_system#0": "The London System builds a reliable dark-square setup with the bishop developed before e3.",
  "opening.london_system#1": "The London System is not only a fixed setup: White must react to Black's structure.",
  "opening.london_system#2": "In London middlegames, a knight on e5 supports direct play with Bd3, Qf3 or Qh5, and a kingside pawn advance.",
  "opening.london_system#3": "When Black plays an early ...Bf5 against the London System, White can challenge that bishop and use Qb3 to…",
  "opening.petroff#0": "The Petroff Defence meets White's central play symmetrically and aims for rapid development rather than…",
  "opening.petroff#1": "Petroff positions often simplify into balanced middlegames, so small improvements matter.",
  "opening.petroff#2": "When White keeps the king in the center in a sharp Petroff branch, Black can use active bishop development…",
  "opening.petroff#3": "Against Petroff move-order sidelines, Black should preserve the defence's character without forcing a…",
  "opening.queens_gambit#0": "The Queen's Gambit family uses the c-pawn to challenge Black's d5-pawn and build central influence.",
  "opening.queens_gambit#1": "Queen's Gambit middlegames are defined by structure.",
  "opening.queens_gambit#2": "In the Queen's Gambit Exchange Variation, White's minority attack with b4-b5 tries to create a fixed…",
  "opening.queens_gambit#3": "In Queen's Gambit Accepted structures, Black usually returns the c4-pawn rather than spending time trying to…",
  "opening.ruy_lopez#0": "The Ruy Lopez increases pressure on Black's e5-pawn while preserving flexible central play.",
  "opening.ruy_lopez#1": "Closed Ruy Lopez positions reward long maneuvers because the center restricts immediate tactics.",
  "opening.ruy_lopez#2": "In the Exchange Ruy Lopez, White can accept the bishop pair to damage Black's queenside pawns and aim for a…",
  "opening.ruy_lopez#3": "In Marshall-style Ruy Lopez positions, Black sacrifices a pawn to accelerate development and attack the…",
  "opening.scandinavian#0": "The Scandinavian Defence challenges White's e4-pawn immediately and forces an early central exchange.",
  "opening.scandinavian#1": "Scandinavian structures often resemble the Caro-Kann or Slav: Black develops the light-squared bishop before…",
  "opening.scandinavian#2": "In ...Qd6 Scandinavian setups, Black's queen supports e5 and kingside castling but can obstruct the…",
  "opening.scandinavian#3": "Scandinavian endgames can favor Black when the opening's early exchange leaves a sound, easy-to-defend…",
  "opening.sicilian#0": "The Sicilian Defence creates an asymmetrical fight: Black exchanges the c-pawn for White's d-pawn and gains…",
  "opening.sicilian#1": "Open Sicilian middlegames often feature opposite-wing attacks.",
  "opening.sicilian#2": "In Najdorf English Attack structures, White often castles queenside and advances f3, g4, and h4, while Black…",
  "opening.sicilian#3": "Against a Maroczy Bind, Black has less space but can build a Hedgehog with pawns on a6, b6, d6, and e6.",
  "piece.blockade#0": "A blockade stops a passed or isolated pawn and turns it into a target.",
  "piece.blockade#1": "Knights are often ideal blockaders because they can attack while occupying the square in front of the pawn.",
  "piece.blockade#2": "Against connected or doubled passers, establish the blockade before they advance with tempo.",
  "piece.centralization#0": "Centralized pieces influence both wings and can switch tasks quickly.",
  "piece.centralization#1": "Centralization is valuable when it supports a pawn break, attacks a weakness, or escorts a passer.",
  "piece.centralization#2": "In a rook-and-pawn ending, place the king diagonally ahead of the passer when possible, support the pawn…",
  "piece.coordination#0": "Pieces are coordinated when they support the same plan, cover one another, and can change roles without…",
  "piece.coordination#1": "A passed pawn becomes dangerous when pieces escort it while controlling blockade squares.",
  "piece.coordination#2": "Before pushing connected passers, assign each piece a task: one controls the blockading square, one covers…",
  "piece.rerouting#0": "When a piece has no useful targets, reroute it toward a stable square that supports the position's main…",
  "piece.rerouting#1": "In symmetrical structures, patient rerouting is often stronger than creating unnecessary pawn weaknesses.",
  "piece.rerouting#2": "A knight stranded on the flank or tied to a pawn can often return through the back rank to a central support…",
  "piece.seventh_rank_invasion#0": "A rook on the seventh rank attacks pawns from the side, restricts the king, and often creates mating or…",
  "piece.seventh_rank_invasion#1": "An invasion is strongest when another piece controls the escape squares or a passed pawn distracts the…",
  "piece.seventh_rank_invasion#2": "In a rook ending, combine a seventh-rank rook with an advancing king that attacks the defender's pawns.",
  "piece.simplification#0": "Simplify when exchanges preserve your advantage and remove the opponent's active resources.",
  "piece.simplification#1": "Trade your bad minor piece for the opponent's good one, or exchange attackers when defending.",
  "piece.simplification#2": "Before entering a pawn ending, verify king access, reserve tempi, and pawn breaks.",
  "positional.color_complexes#0": "Pawn moves permanently weaken squares of one color.",
  "positional.color_complexes#1": "Judge a color complex through the pawn structure and bishop placement, not the exact position alone.",
  "positional.color_complexes#2": "When kingside pawns are fixed on dark squares and the dark-squared bishop is absent, build a…",
  "positional.outpost#0": "An outpost is a useful square that cannot be challenged safely by an enemy pawn.",
  "positional.outpost#1": "Pawn structure determines outposts.",
  "positional.outpost#2": "Before installing a knight on a central outpost, prevent the pawn break that would undermine its support and…",
  "positional.pawn_break#0": "A pawn break should open a line, challenge a chain, create a passer, or gain a useful square.",
  "positional.pawn_break#1": "Identify whether to attack the head or base of the pawn chain.",
  "positional.pawn_break#2": "With hanging pawns, time the central advance while both pawns are defended and your pieces can use the…",
  "positional.prophylaxis#0": "Prophylaxis means preventing the opponent's plan before it becomes a direct threat.",
  "positional.prophylaxis#1": "In a familiar structure, identify the lever that releases the opponent's cramped pieces.",
  "positional.prophylaxis#2": "Against an IQP, prevent the liberating advance before piling up on the pawn.",
  "positional.restriction#0": "Restriction reduces the opponent's useful moves before you attack.",
  "positional.restriction#1": "A spatial advantage matters when the pawn structure denies good squares to enemy pieces.",
  "positional.restriction#2": "If control of e5 dominates the position, reinforce that square, neutralize the defender that contests it,…",
  "positional.two_weaknesses#0": "One weakness can often be defended.",
  "positional.two_weaknesses#1": "Fix the first target before switching wings.",
  "positional.two_weaknesses#2": "When a kingside pawn is already weak, provoke a queenside pawn into becoming a second target.",
  "structure.carlsbad#0": "In the Carlsbad structure, plans come from the fixed central pawn skeleton: a queenside minority attack,…",
  "structure.carlsbad#1": "The minority attack uses fewer queenside pawns to provoke a backward or isolated pawn.",
  "structure.carlsbad#2": "Before the Carlsbad b-pawn break, place rooks on the files likely to open and ensure a knight can occupy the…",
  "structure.caro_slav#0": "The Caro-Slav family is defined by one side's advanced d-pawn against a restrained opposing center.",
  "structure.caro_slav#1": "In Caro-Slav structures, compare breaks against the front of the chain with breaks against its base.",
  "structure.caro_slav#2": "If an advanced e-pawn merely blocks your bishop and rook, returning or sacrificing it can restore…",
  "structure.doubled_pawns#0": "Doubled pawns are weaknesses only when they can be attacked or cannot create useful control.",
  "structure.doubled_pawns#1": "In an ending, fix doubled pawns before attacking them.",
  "structure.doubled_pawns#2": "Do not repair doubled kingside pawns automatically if they still halt an enemy majority and remain easy for…",
  "structure.dragon_formation#0": "The Dragon formation features a kingside fianchetto aimed at a center that may open.",
  "structure.dragon_formation#1": "Dragon positions should be recognized by structure even with colors reversed.",
  "structure.dragon_formation#2": "Against a Maróczy-style bind, the Dragon bishop needs a pawn break to become active.",
  "structure.hanging_pawns#0": "Hanging pawns offer space and dynamic breaks but can become fixed targets.",
  "structure.hanging_pawns#1": "The side with hanging pawns should prepare a central advance or kingside activity.",
  "structure.hanging_pawns#2": "Before simplifying a hanging-pawn position, check whether exchanges remove the pieces that support the…",
  "structure.hedgehog#0": "The Hedgehog accepts less space in return for a compact pawn shell and prepared counterbreaks.",
  "structure.hedgehog#1": "The Hedgehog player seeks freeing central or queenside breaks; the space-advantaged side restrains them and…",
  "structure.hedgehog#2": "In a Hedgehog, place rooks and queen behind the central breaks and reroute a knight toward active kingside…",
  "structure.iqp#0": "An IQP grants space, open lines, and active piece play, but becomes a long-term target if its advance is…",
  "structure.iqp#1": "The IQP side should coordinate pieces for the liberating advance or a kingside attack.",
  "structure.iqp#2": "Before advancing an IQP, unpin the supporting knight and prevent the opponent's favorable bishop development…",
  "structure.maroczy_bind#0": "The Maróczy Bind uses central pawns to restrict freeing breaks and limit opposing pieces.",
  "structure.maroczy_bind#1": "The cramped side seeks timely pawn breaks and piece exchanges; the side with the Maróczy Bind controls those…",
  "structure.maroczy_bind#2": "A knight reroute toward a stable queenside or central square can reinforce the Maróczy Bind while freeing…",
  "structure.passed_pawn#0": "A passed pawn is valuable because it demands a blockade and ties down pieces.",
  "structure.passed_pawn#1": "Create a passed pawn by fixing the opposing majority, opening the correct file, or forcing a favorable…",
  "structure.passed_pawn#2": "Against a passed pawn, establish the blockade with the king or bishop before attacking its base.",
  "structure.pawn_chain#0": "In a locked center, pawn chains determine space, breaks, and piece routes.",
  "structure.pawn_chain#1": "A closed center gives time to reroute pieces toward the wing where the chain points.",
  "structure.pawn_chain#2": "When one lever attacks the front pawn and another attacks the base, compare which exchange opens the useful…",
  "structure.scheveningen#0": "The Scheveningen small center is flexible but compact.",
  "structure.scheveningen#1": "Recognize the Scheveningen by the central pawn structure, whether reached from the Najdorf, Kan, or Taimanov.",
  "structure.scheveningen#2": "Before the Scheveningen f-pawn break, ensure the e-pawn remains defended and the dark squares around the…",
  "endgame.strategic.opposite_bishops#0": "With opposite-colored bishops, the side with the initiative should attack on the color complex the opponent…",
  "endgame.strategic.opposite_bishops#1": "The defender should place pawns on the color of their bishop, blockade passed pawns on the enemy bishop's…",
  "endgame.strategic.opposite_bishops#2": "To win opposite-bishop middlegames, combine kingside pressure with a queenside passer or a second weakness."
}

def key_meta(key_id: str) -> dict[str, Any]:
    return CANON_KEY_META.get(key_id, {})

def note_compact(key_id: str, index: int) -> str:
    rows = NOTE_COMPACT_BY_KEY.get(key_id) or []
    if 0 <= index < len(rows):
        return rows[index]
    return NOTE_COMPACT.get(f"{key_id}#{index}", "")
