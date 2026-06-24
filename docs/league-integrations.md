# League integrations

Skipper can connect a team to an external league schedule. Today the built-in integration is **`lfbq_spordle`** (LFBQ on Spordle).

Configure per team in `backend/app/tenants.json`:

```json
{
  "name": "My Team 13U",
  "integration_version": "lfbq_spordle",
  "integration_config": {
    "our_spordle_team_id": 167215,
    "page_slug": "ligue-feminine-de-baseball-du-quebec",
    "page_id": "1ed21b23-724b-6b80-b13c-06bf14840f98",
    "locale": "fr",
    "schedules": [
      {
        "schedule_id": 193093,
        "game_type": "season",
        "label": "Regular season"
      },
      {
        "schedule_id": 195112,
        "game_type": "postseason",
        "label": "Playoffs"
      },
      {
        "schedule_id": 196000,
        "game_type": "tournament",
        "label": "Provincial"
      }
    ]
  }
}
```

After changing `tenants.json`, redeploy (or restart locally). Startup syncs integration settings into the database.

## What each field does

| Field | Required for | Description |
|-------|----------------|-------------|
| `schedules` | Sync (recommended) | List of Spordle schedules for this team. Each entry has `schedule_id`, `game_type` (`season`, `postseason`, or `tournament`), and optional `label`. |
| `schedule_id` | Sync (legacy) | Single schedule ID. Still supported; treated as one `season` schedule when `schedules` is omitted. |
| `our_spordle_team_id` | Sync, opponent intel | Your team’s Spordle team ID. Same across all schedules for the same roster. |
| `page_slug` | Spordle links | League slug in Spordle Page URLs (`page.spordle.com/fr/{page_slug}/…`). |
| `page_id` | Config discovery only | Category UUID from the division standings URL — used to find `schedule_id`, not for game/team links. |
| `locale` | Spordle links | `fr` or `en` in the link (defaults to `fr`). |

**Sync** needs `our_spordle_team_id` plus at least one schedule (`schedules` or legacy `schedule_id`). Sync imports from every configured schedule and sets each new game’s `game_type` from its schedule entry.

**Opponent intel** needs the same team ID plus a `season` schedule. Standings and recent opponent games always come from the season schedule, even when previewing a playoff or tournament game. The current game is resolved across all configured schedules so Spordle links still work.

**Spordle links** in opponent intel need `page_slug` (and `locale`). Links use these public URL patterns:

```
https://page.spordle.com/fr/{page_slug}/schedule/{spordle_game_id}
https://page.spordle.com/fr/{page_slug}/teams/{spordle_team_id}
```

Example game: [`…/schedule/846892`](https://page.spordle.com/fr/ligue-feminine-de-baseball-du-quebec/schedule/846892)  
Example team: [`…/teams/163211`](https://page.spordle.com/fr/ligue-feminine-de-baseball-du-quebec/teams/163211)

## Finding values from a Spordle URL

Open your division on [page.spordle.com](https://page.spordle.com), then copy from the address bar:

```
https://page.spordle.com/fr/{page_slug}/schedule-stats-standings/{page_id}?tab=schedule&scheduleId={schedule_id}
```

Example:

```
https://page.spordle.com/fr/ligue-feminine-de-baseball-du-quebec/schedule-stats-standings/1ed21b23-724b-6b80-b13c-06bf14840f98?tab=standings&scheduleId=193093
```

| From URL | Config key |
|----------|------------|
| `ligue-feminine-de-baseball-du-quebec` | `page_slug` |
| `1ed21b23-724b-6b80-b13c-06bf14840f98` | `page_id` |
| `193093` | `schedule_id` inside a `schedules` entry (or legacy top-level `schedule_id`) |
| `fr` (path segment) | `locale` |

`our_spordle_team_id` is not in the URL. On Spordle, open your team’s schedule and note the team from a game row, or query the Play API schedule and match your team name to its `id`.

## Features enabled

With `lfbq_spordle` configured:

- **Sync schedule** (Games page) — imports/updates games from every configured Spordle schedule; new games get `game_type` from their schedule entry (`season`, `postseason`, or `tournament`). Does not overwrite game mode or game type on existing games.
- **Opponent intel** (game overview) — standing, runs per game, and last 5 completed opponent games from the **season** schedule only; works for upcoming games from any configured schedule.

Optional env var: `SPORDLE_API_KEY` (defaults to the public Play API key used by Spordle Page).
