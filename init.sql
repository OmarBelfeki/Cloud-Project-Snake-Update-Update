-- init.sql
-- This file will be executed when MySQL container starts

-- Create additional indexes for performance
CREATE INDEX IF NOT EXISTS idx_players_last_seen ON players(last_seen DESC);
CREATE INDEX IF NOT EXISTS idx_game_sessions_player_date ON game_sessions(player_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_high_scores_achieved ON high_scores(achieved_at DESC);

-- Create views for common queries
CREATE OR REPLACE VIEW v_player_rankings AS
SELECT
    p.player_id,
    p.display_name,
    p.highest_score,
    p.total_games,
    p.total_score,
    RANK() OVER (ORDER BY p.highest_score DESC) as rank_by_score,
    RANK() OVER (ORDER BY p.total_games DESC) as rank_by_games
FROM players p;

CREATE OR REPLACE VIEW v_daily_leaderboard AS
SELECT
    DATE(gs.created_at) as game_date,
    p.player_id,
    p.display_name,
    MAX(gs.score) as daily_best_score,
    COUNT(*) as games_played
FROM game_sessions gs
JOIN players p ON gs.player_id = p.player_id
WHERE gs.created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
GROUP BY DATE(gs.created_at), p.player_id, p.display_name;

-- Create stored procedure for player cleanup
DELIMITER //
CREATE PROCEDURE sp_cleanup_inactive_players(IN days_inactive INT)
BEGIN
    DECLARE cutoff_date DATE;
    SET cutoff_date = DATE_SUB(CURDATE(), INTERVAL days_inactive DAY);

    -- Archive inactive players before deletion
    INSERT INTO players_archive
    SELECT *, CURDATE() as archived_date
    FROM players
    WHERE last_seen < cutoff_date;

    -- Delete inactive players
    DELETE FROM players WHERE last_seen < cutoff_date;

    SELECT ROW_COUNT() as players_deleted;
END //
DELIMITER ;