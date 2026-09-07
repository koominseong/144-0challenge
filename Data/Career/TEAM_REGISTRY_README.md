# Career Team Registry

Career Mode uses `team_id` as the single source of truth.

## Canonical chain

`team_id -> career_teams.json name -> career_team_registry.json logo_file`

Example:

`MLB_14 -> Los Angeles Dodgers -> team_logo_MLB_14.jpg`

## Rules

- Templates must never build a logo filename from `logo_key` or display name.
- History rows keep `team_id`, and the displayed team name is resolved from the registry.
- Existing saves are normalized when loaded/saved, so stale team names are replaced by the canonical name for the same `team_id`.
- To replace a logo with an official asset, overwrite the corresponding `team_logo_<TEAM_ID>.jpg` file. No Python/HTML change is required.
