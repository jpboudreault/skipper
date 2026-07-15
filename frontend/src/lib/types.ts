/**
 * Shared API types mirroring the backend SQLModel schemas and stats payloads
 * (see backend/app/models.py and backend/app/stats.py). These let pages drop
 * `any` typing and catch shape mismatches at `npm run check` time.
 */

export interface Team {
	id: number;
	name: string;
	season: string;
	innings_per_game: number;
	max_pitcher_innings_per_game: number;
	max_pitcher_innings_per_7_days: number;
	late_inning_weight: number;
	language: string;
	division?: string | null;
	classe?: string | null;
	default_league?: string | null;
	lineup_print_version: string;
	scoresheet_version: string;
	integration_version?: string | null;
}

export interface Player {
	id: number;
	team_id: number;
	first_name: string;
	last_name: string;
	jersey: number;
	default_batting_order?: number | null;
	active: boolean;
	is_substitute: boolean;
	is_coach: boolean;
	coach_type?: string | null;
}

export type GameMode = 'compete' | 'develop' | 'optimal';
export type GameType = 'season' | 'postseason' | 'tournament';

export interface Game {
	id: number;
	team_id: number;
	date: string;
	game_number?: string | null;
	opponent?: string | null;
	venue?: string | null;
	home_away?: 'H' | 'A' | null;
	innings_played?: number | null;
	result_runs_for?: number | null;
	result_runs_against?: number | null;
	mode: GameMode;
	game_type: GameType;
	league?: string | null;
	notes?: string | null;
	schedule_status?: string | null;
	external_source?: string | null;
	external_game_id?: string | null;
}

export type AvailabilityStatus = 'available' | 'absent' | 'late' | 'injured';

export interface Availability {
	game_id: number;
	player_id: number;
	status: AvailabilityStatus;
	injury_inning?: number | null;
}

export interface BattingLine {
	game_id: number;
	player_id: number;
	batting_order?: number | null;
	singles: number;
	doubles: number;
	triples: number;
	hr: number;
	bb: number;
	bbi: number;
	hbp: number;
	sac: number;
	intf: number;
	kd: number;
	ke: number;
	outs_not_k: number;
	fc: number;
	roe: number;
	rbi: number;
	r: number;
	sb: number;
}

export interface PitchingAppearance {
	id?: number;
	game_id: number;
	player_id: number;
	inning_entered: number;
	inning_exited: number;
	ip_outs: number;
	runs_allowed: number;
	k: number;
	bb: number;
	hbp: number;
	pitch_count?: number | null;
}

export interface LineupCell {
	game_id?: number;
	inning: number;
	player_id: number;
	position: number; // 0 = bench, 1-9 = field
	locked: boolean;
}

export interface PositionScore {
	player_id: number;
	position: number;
	score: number;
	is_forbidden: boolean;
}

export interface BattingStat {
	player_id: number;
	name: string;
	jersey: number;
	pa: number;
	ab: number;
	h: number;
	singles: number;
	doubles: number;
	triples: number;
	hr: number;
	bb: number;
	bbi: number;
	hbp: number;
	sac: number;
	intf: number;
	kd: number;
	ke: number;
	outs_not_k: number;
	fc: number;
	roe: number;
	rbi: number;
	r: number;
	sb: number;
	avg: number;
	obp: number;
	slg: number;
	ops: number;
}

export interface PitchingStat {
	player_id: number;
	name: string;
	jersey: number;
	ip_outs: number;
	ip: number;
	ip_display: string;
	runs_allowed: number;
	k: number;
	bb: number;
	hbp: number;
	appearances: number;
	k_9: number;
	bb_9: number;
	hbp_9: number;
	r_9: number;
}

export interface PositionStat {
	player_id: number;
	name: string;
	jersey: number;
	positions: Record<string, number>;
	total_innings: number;
	bench_pct: number;
}

export interface CumulativeBattingPoint {
	game_id: number;
	date: string;
	opponent: string | null;
	avg: number;
	obp: number;
	slg: number;
	ops: number;
}

export interface PositionVarietyRow {
	player_id: number;
	name: string;
	jersey: number;
	distinct_positions: number;
	total_innings: number;
	bench_pct: number;
}

export interface DevelopmentTrends {
	cumulative_batting: CumulativeBattingPoint[];
	position_variety: PositionVarietyRow[];
}

export interface PitcherStatus {
	player_id: number;
	jersey: number;
	name: string;
	eligible: boolean;
	reason: string;
	innings_today: number;
	innings_last_7_days: number;
	remaining_today: number;
	remaining_7_days: number;
	pitches_today: number;
	remaining_pitches_today: number | null;
	rest_until: string | null;
}
