# Working in this repository (humans and agents)

Multi-agent CAD here is ordinary Git. There is no coordination server, lock or shared
session: a part is a text file, a change is a branch, a proposal is a pull request, and CI
is the reviewer that decides whether the geometry exists.

## The protocol

1. **One part per file.** A part is `parts/<name>.firmament`. Its file name is its identity;
   the build writes `<name>.step`, `<name>.stl` and a drawing for it.
2. **One agent per branch.** Name branches `<agent>/<part-or-change>`, for example
   `claude/mounting-plate` or `codex/starter-plate-slots`. Two agents never commit to the same
   branch; they coordinate through pull requests and review comments, like people do.
3. **Change someone else's part only through a pull request.** The diff is the review: a
   dimension change is a one-line diff with units on it.
4. **CI is the oracle, not the author.** The `Build parts` workflow compiles every part with
   the pinned compiler in `aetheris-revision.txt`. A part that fails validation fails the
   check, with the compiler's diagnostic and line in the run summary. Do not claim a part
   works until that check is green; fix the source until it is.
5. **Read the result, not just the status.** The run summary lists each part's feature
   count and drawing kind. Download the `parts-<commit>` artifact to inspect the STEP and
   PDF. A `reference-only` drawing means the automatic dimension planner could not fully
   define the part; it is labelled *not for manufacture* on the sheet.
6. **Leave the bracket pipeline alone unless asked.** `src/`, `scripts/Qualify.ps1` and the
   bracket workflow qualify the flagship bracket and its revision reviews. Changes to
   `parts/` do not trigger that pipeline.

## Writing Firmament

- Every length carries a unit (`8mm`); `Units: mm` is required in a part.
- Start from `parts/starter-plate.firmament`. A Box with through holes from `+Z` gets a
  fully dimensioned drawing automatically.
- For outlines other than a rectangle, use a Profile and Compose, as in
  `parts/claude-mounting-plate.firmament`. Round vertical edges in the Profile
  (`RoundedRect2`); `EdgeFinish` only finishes the edges around one face.
- The language reference lives in the Aetheris repository under
  `docs/public/reference/language/`. The compiler is the authority: when the docs and
  `aetheris validate --json` disagree, the compiler wins and the docs need a fix.

## Commit attribution

Agents identify themselves in commits. Use the agent name as the author or add a
`Co-Authored-By:` trailer, so `git log -- parts/<name>.firmament` shows who designed what.
