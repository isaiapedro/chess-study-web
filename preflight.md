# Chess Coach Preflight

## Ollama

- OK embed model nomic-embed-text dims=768
- OK chat model present: qwen3:8b

## Books

Checked 41 files — 26 OK, 15 need attention. Est. chunks≈47761.

- [OK] `Capablancas Best Chess Endings (José Raúl Capablanca, Irving Chernev) (Z-Library).pdf` | 302p | sample=5785c | chunks≈776 | sidecar=capablancas_best_chess_endings.themes.yaml
  themes: endgame
  - text extract looks usable
  - sidecar matched: capablancas_best_chess_endings.themes.yaml
- [BAD] `Chess Strategy for Club Players.pdf` | 413p | sample=7c | chunks≈1062 | sidecar=chess_strategy_for_club_players.themes.yaml
  - likely scanned/empty OCR — extract almost empty
  - sidecar matched: chess_strategy_for_club_players.themes.yaml
- [OK] `Chess Structures A Grandmaster Guide - Standard Patterns and Plans Explained (Mauricio Flores Rios) (Z-Library).pdf` | 466p | sample=10907c | chunks≈1198 | sidecar=chess_structures_a_grandmaster_guide.themes.themes.yaml
  themes: isolated queen pawn, hanging pawns, sicilian
  - text extract looks usable
  - sidecar matched: chess_structures_a_grandmaster_guide.themes.themes.yaml
- [OK] `Dvoretskys Endgame Manual Fifth Edition (Mark Dvoretsky (Revised by Karsten Müller)) (z-library.sk, 1lib.sk, z-lib.sk).pdf` | 1231p | sample=4924c | chunks≈3165 | sidecar=dvoretskys_endgame_manual.themes.yaml
  themes: passed pawn, endgame
  - text extract looks usable
  - sidecar matched: dvoretskys_endgame_manual.themes.yaml
- [OK] `Everyones First Chess Workbook Fundamental Tactics and Checkmates for Improvers - 738 Practical Exercises (Peter Giannatos etc.) (z-library.sk, 1lib.sk, z-lib.sk).pdf` | 1136p | sample=1694c | chunks≈2921 | sidecar=-
  - text extract looks usable
  - no sidecar (themes from text only)
- [BAD] `Excelling at Chess Calculation (Jacob Aagaard) (Z-Library).pdf` | 194p | sample=7c | chunks≈498 | sidecar=excelling_at_chess_calculation.themes.yaml
  - likely scanned/empty OCR — extract almost empty
  - sidecar matched: excelling_at_chess_calculation.themes.yaml
- [OK] `FCO Fundamental Chess Openings (Paul van der Sterren) (Z-Library).pdf` | 480p | sample=11102c | chunks≈1234 | sidecar=fco_fundamental_chess_openings.themes.yaml
  themes: endgame, sicilian
  - text extract looks usable
  - sidecar matched: fco_fundamental_chess_openings.themes.yaml
- [OK] `Grandmaster Repertoire 1A ‒ 1.d4 The Catalan (Boris Avrukh) (Z-Library).pdf` | 442p | sample=7172c | chunks≈1136 | sidecar=grandmaster_repertoire_1A.themes.yaml
  - text extract looks usable
  - sidecar matched: grandmaster_repertoire_1A.themes.yaml
- [BAD] `Grandmaster Repertoire 3 The English Opening Volume One ( etc.) (Z-Library).pdf` | 482p | sample=7c | chunks≈1239 | sidecar=grandmaster_repertoire_3.themes.yaml
  - likely scanned/empty OCR — extract almost empty
  - sidecar matched: grandmaster_repertoire_3.themes.yaml
- [BAD] `Grandmaster Repertoire 4 The English Opening Volume Two ( etc.) (Z-Library).pdf` | 431p | sample=7c | chunks≈1108 | sidecar=grandmaster_repertoire_4.themes.yaml
  - likely scanned/empty OCR — extract almost empty
  - sidecar matched: grandmaster_repertoire_4.themes.yaml
- [OK] `Grandmaster Repertoire 5 - The English Opening - Volume Three (Mihail Marin etc.) (Z-Library).pdf` | 272p | sample=6197c | chunks≈699 | sidecar=grandmaster_repertoire_5.themes.yaml
  - text extract looks usable
  - sidecar matched: grandmaster_repertoire_5.themes.yaml
- [OK] `Jeremy Silman - How To Reassess Your Chess.pdf` | 1001p | sample=3828c | chunks≈2574 | sidecar=how_to_reassess_your_chess.themes.yaml
  themes: passed pawn, open file, bishop pair, king safety, endgame, sicilian
  - text extract looks usable
  - sidecar matched: how_to_reassess_your_chess.themes.yaml
- [OK] `Kings Indian Warfare (Ilya Smirin) (Z-Library).pdf` | 354p | sample=6617c | chunks≈910 | sidecar=kings_indian_warfare.themes.yaml
  themes: endgame
  - text extract looks usable
  - sidecar matched: kings_indian_warfare.themes.yaml
- [BAD] `Logical Chess Move By Move Every Move explained (Irving Chernev) (z-library.sk, 1lib.sk, z-lib.sk).pdf` | 256p | sample=7c | chunks≈658 | sidecar=logical_chess.themes.yaml
  - likely scanned/empty OCR — extract almost empty
  - sidecar matched: logical_chess.themes.yaml
- [OK] `Maneuvering the art of piece play (Dvoret︠s︡kiĭ, Mark Izrailevich) (Z-Library).pdf` | 215p | sample=10800c | chunks≈552 | sidecar=maneuvering_the_art_of_piece_play.themes.yaml
  themes: endgame
  - text extract looks usable
  - sidecar matched: maneuvering_the_art_of_piece_play.themes.yaml
- [BAD] `Mastering Chess Strategy (Johan Hellsten) (Z-Library).pdf` | 491p | sample=7c | chunks≈1262 | sidecar=mastering_chess_strategy.themes.yaml
  - likely scanned/empty OCR — extract almost empty
  - sidecar matched: mastering_chess_strategy.themes.yaml
- [OK] `Mastering Endgame Strategy (Johan Hellsten) (z-library.sk, 1lib.sk, z-lib.sk).pdf` | 484p | sample=12000c | chunks≈1244 | sidecar=mastering_endgame_strategy.themes.yaml
  themes: endgame, sicilian
  - text extract looks usable
  - sidecar matched: mastering_endgame_strategy.themes.yaml
- [OK] `Mastering Opening Strategy (Johan Hellsten) (Z-Library).pdf` | 367p | sample=7565c | chunks≈943 | sidecar=mastering_opening_strategy.themes.yaml
  themes: endgame, sicilian
  - text extract looks usable
  - sidecar matched: mastering_opening_strategy.themes.yaml
- [BAD] `My 60 Memorable Games (Bobby Fischer) (Z-Library).pdf` | 382p | sample=7c | chunks≈982 | sidecar=my_60_memorable_games.themes.yaml
  - likely scanned/empty OCR — extract almost empty
  - sidecar matched: my_60_memorable_games.themes.yaml
- [OK] `My Best Games of Chess 1908-1937 (Alexander Alekhine) (Z-Library).pdf` | 766p | sample=9492c | chunks≈1969 | sidecar=my_best_games_of_chess_1908_1937.themes.yaml
  themes: endgame, sicilian
  - text extract looks usable
  - sidecar matched: my_best_games_of_chess_1908_1937.themes.yaml
- [OK] `My Great Predecessors 2 (Kasparov, Garry) (Z-Library).pdf` | 483p | sample=12000c | chunks≈1242 | sidecar=my_great_predecessors_2.themes.yaml
  - text extract looks usable
  - sidecar matched: my_great_predecessors_2.themes.yaml
- [OK] `My Great Predecessors 3. (Kasparov, Garry) (Z-Library).pdf` | 334p | sample=10084c | chunks≈858 | sidecar=my_great_predecessors_3.themes.yaml
  - text extract looks usable
  - sidecar matched: my_great_predecessors_3.themes.yaml
- [OK] `My Great Predecessors 4 (Kasparov, Garry) (Z-Library).pdf` | 498p | sample=11918c | chunks≈1280 | sidecar=my_great_predecessors_4.themes.yaml
  themes: sicilian
  - text extract looks usable
  - sidecar matched: my_great_predecessors_4.themes.yaml
- [BAD] `Pawn power in chess (Hans Kmoch) (z-library.sk, 1lib.sk, z-lib.sk).pdf` | 274p | sample=7c | chunks≈704 | sidecar=pawn_power_in_chess.themes.yaml
  - likely scanned/empty OCR — extract almost empty
  - sidecar matched: pawn_power_in_chess.themes.yaml
- [OK] `Pawn structure chess (Soltis, Andy) (z-library.sk, 1lib.sk, z-lib.sk).pdf` | 300p | sample=7257c | chunks≈771 | sidecar=-
  themes: minority attack, king safety, sicilian
  - text extract looks usable
  - no sidecar (themes from text only)
- [OK] `Playing the Petroff (Swapnil, Dhopade) (Z-Library).pdf` | 657p | sample=8669c | chunks≈1689 | sidecar=playing_the_petroff.themes.yaml
  themes: endgame
  - text extract looks usable
  - sidecar matched: playing_the_petroff.themes.yaml
- [OK] `Positional Decision Making in Chess (Grandmaster Repertoire Series) (Boris Gelfand) (z-library.sk, 1lib.sk, z-lib.sk).pdf` | 290p | sample=7954c | chunks≈745 | sidecar=positional_decision_making_in_chess.themes.yaml
  - text extract looks usable
  - sidecar matched: positional_decision_making_in_chess.themes.yaml
- [OK] `Pump Up Your Rating (Axel Smith) (Z-Library).pdf` | 378p | sample=11760c | chunks≈972 | sidecar=pump_up_your_rating.themes.yaml
  themes: endgame
  - text extract looks usable
  - sidecar matched: pump_up_your_rating.themes.yaml
- [OK] `Secrets of Positional Play School of Future Champions Volume 4 (Mark Dvoretsky etc.) (z-library.sk, 1lib.sk, z-lib.sk).pdf` | 242p | sample=11373c | chunks≈622 | sidecar=secrets_of_positional_play.themes.yaml
  themes: endgame
  - text extract looks usable
  - sidecar matched: secrets_of_positional_play.themes.yaml
- [BAD] `Silmans Complete Endgame Course From Beginner to Master (Jeremy Silman) (z-library.sk, 1lib.sk, z-lib.sk).pdf` | 543p | sample=7c | chunks≈1396 | sidecar=silmans_complete_endgame_course.themes.yaml
  - likely scanned/empty OCR — extract almost empty
  - sidecar matched: silmans_complete_endgame_course.themes.yaml
- [OK] `Small Steps to Giant Improvement Master Pawn Play in Chess (Sam Shankland) (Z-Library).pdf` | 337p | sample=5508c | chunks≈866 | sidecar=small_steps_to_giant_improvement.themes.yaml
  - text extract looks usable
  - sidecar matched: small_steps_to_giant_improvement.themes.yaml
- [BAD] `The Art of Attack in Chess (Vladimir Vukovic) (Z-Library).pdf` | 350p | sample=7c | chunks≈900 | sidecar=the_art_of_attack_in_chess.themes.yaml
  - likely scanned/empty OCR — extract almost empty
  - sidecar matched: the_art_of_attack_in_chess.themes.yaml
- [OK] `The Caro-Kann Move by Move (Cyrus Lakdawala) (Z-Library).pdf` | 434p | sample=8241c | chunks≈1116 | sidecar=the_caro_kann_move_by_move.themes.yaml
  themes: hanging pawns, piece activity
  - text extract looks usable
  - sidecar matched: the_caro_kann_move_by_move.themes.yaml
- [BAD] `The Chess Games of Adolph Anderssen Master of Attack (Sid Pickard) (Z-Library).pdf` | 345p | sample=7c | chunks≈887 | sidecar=-
  - likely scanned/empty OCR — extract almost empty
  - no sidecar (themes from text only)
- [OK] `The Life and Games of Mikhail Tal (Mikhail Tal [Tal, Mikhail]) (Z-Library).pdf` | 717p | sample=4533c | chunks≈1843 | sidecar=the_life_and_games_of_mikhail_tal.themes.yaml
  - text extract looks usable
  - sidecar matched: the_life_and_games_of_mikhail_tal.themes.yaml
- [OK] `Think Like a Super-GM (Michael Adams, Philip Hurtado) (Z-Library).pdf` | 700p | sample=9477c | chunks≈1800 | sidecar=think_like_a_super_gm.themes.yaml
  - text extract looks usable
  - sidecar matched: think_like_a_super_gm.themes.yaml
- [BAD] `Understanding Chess Move by Move (John Nunn) (Z-Library).pdf` | 239p | sample=7c | chunks≈614 | sidecar=understanding_chess_move_by_move.themes.yaml
  - likely scanned/empty OCR — extract almost empty
  - sidecar matched: understanding_chess_move_by_move.themes.yaml
- [OK] `Win with the Caro-Kann (Sverres Chess Openings) (Sverre Johnsen, Torbjorn Ringdal Hansen) (Z-Library).pdf` | 737p | sample=4111c | chunks≈1895 | sidecar=win_with_the_caro_kann.themes.yaml
  - text extract looks usable
  - sidecar matched: win_with_the_caro_kann.themes.yaml
- [BAD] `Win with the London System (Sverre Johnsen, Vlatko Kovacevic) (Z-Library).pdf` | 178p | sample=7c | chunks≈457 | sidecar=win_with_the_london_system.themes.yaml
  - likely scanned/empty OCR — extract almost empty
  - sidecar matched: win_with_the_london_system.themes.yaml
- [BAD] `Zurich International Chess Tournament, 1953 (David Bronstein, Jim Marfia) (z-library.sk, 1lib.sk, z-lib.sk).pdf` | 186p | sample=7c | chunks≈478 | sidecar=zurich_international_chess_tournament.themes.yaml
  - likely scanned/empty OCR — extract almost empty
  - sidecar matched: zurich_international_chess_tournament.themes.yaml
- [BAD] `understanding_the_scandinavian.pdf` | 193p | sample=7c | chunks≈496 | sidecar=understanding_the_scandinavian.themes.yaml
  - likely scanned/empty OCR — extract almost empty
  - sidecar matched: understanding_the_scandinavian.themes.yaml

## Before full ingest
1. Fix BAD books (OCR / export to `.txt` if PDF extract empty).
2. Confirm Ollama embed line says OK with dims (real embeddings).
3. Pilot one book first:
   `chess-coach ingest "data/books/Logical Chess....pdf" --reset`
4. Spot-check retrieve, then full archive:
   `chess-coach ingest data/books --reset`
