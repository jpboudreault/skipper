# League integrations

Skipper can connect a team to an external league schedule. Today the built-in integration is **`lfbq_spordle`** (LFBQ on Spordle).

Configure per team in `backend/app/tenants.json`:

```json
{
  "name": "My Team 13U",
  "integration_version": "lfbq_spordle",
  "integration_config": {
    "schedule_id": 193093,
    "our_spordle_team_id": 167215,
    "page_slug": "ligue-feminine-de-baseball-du-quebec",
    "page_id": "1ed21b23-724b-6b80-b13c-06bf14840f98",
    "locale": "fr"
  }
}
```

After changing `tenants.json`, redeploy (or restart locally). Startup syncs integration settings into the database.

## What each field does

| Field | Required for | Description |
|-------|----------------|-------------|
| `schedule_id` | Sync, opponent intel, Spordle links | Numeric schedule ID for your division (e.g. 13U B vs 15U B). |
| `our_spordle_team_id` | Sync, opponent intel | Your team’s Spordle team ID. Unique per roster. |
| `page_slug` | Spordle links | League slug in Spordle Page URLs (`page.spordle.com/fr/{page_slug}/…`). |
| `page_id` | Config discovery only | Category UUID from the division standings URL — used to find `schedule_id`, not for game/team links. |
| `locale` | Spordle links | `fr` or `en` in the link (defaults to `fr`). |

**Sync and opponent intel** need `schedule_id` + `our_spordle_team_id`.

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
| `193093` | `schedule_id` |
| `fr` (path segment) | `locale` |

`our_spordle_team_id` is not in the URL. On Spordle, open your team’s schedule and note the team from a game row, or query the Play API schedule and match your team name to its `id`.

## Features enabled

With `lfbq_spordle` configured:

- **Sync schedule** (Games page) — imports/updates games from Spordle; does not overwrite game mode or game type on existing games.
- **Opponent intel** (game overview) — standing, runs per game, last 5 completed opponent games, links to Spordle.

Optional env var: `SPORDLE_API_KEY` (defaults to the public Play API key used by Spordle Page).
