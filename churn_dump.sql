DROP TABLE IF EXISTS churn_overview;
CREATE TABLE churn_overview (
            game_id         TEXT PRIMARY KEY,
            total_players   INTEGER,
            churned_players INTEGER,
            active_players  INTEGER,
            churn_rate      REAL,
            churn_cutoff    TEXT
        );

DROP TABLE IF EXISTS churn_exit_type;
CREATE TABLE churn_exit_type (
            game_id       TEXT,
            exit_type     TEXT,
            label         TEXT,
            player_count  INTEGER,
            pct           REAL,
            PRIMARY KEY (game_id, exit_type)
        );

DROP TABLE IF EXISTS churn_last_days;
CREATE TABLE churn_last_days (
            game_id          TEXT,
            day_rank         INTEGER,
            n_players        INTEGER,
            avg_win_ratio    REAL,
            avg_exit_balance REAL,
            pct_losing       REAL,
            PRIMARY KEY (game_id, day_rank)
        );

INSERT INTO churn_overview VALUES ('101003', 451991, 363930, 88061, 0.8051708994205636, '2026-03-11');
INSERT INTO churn_overview VALUES ('102003', 745465, 599592, 145873, 0.8043194516174468, '2026-03-11');

INSERT INTO churn_exit_type VALUES ('101003', 'busted', '輸光 (WinRatio < 0.1)', 158709, 39.4);
INSERT INTO churn_exit_type VALUES ('101003', 'heavy_loss', '重損 (0.1 ~ 0.5)', 42289, 10.5);
INSERT INTO churn_exit_type VALUES ('101003', 'light_loss', '小輸 (0.5 ~ 1.0)', 110625, 27.46);
INSERT INTO churn_exit_type VALUES ('101003', 'profit', '贏錢離場 (≥ 1.0)', 91175, 22.64);
INSERT INTO churn_exit_type VALUES ('102003', 'busted', '輸光 (WinRatio < 0.1)', 254912, 38.51);
INSERT INTO churn_exit_type VALUES ('102003', 'heavy_loss', '重損 (0.1 ~ 0.5)', 66103, 9.99);
INSERT INTO churn_exit_type VALUES ('102003', 'light_loss', '小輸 (0.5 ~ 1.0)', 172119, 26.0);
INSERT INTO churn_exit_type VALUES ('102003', 'profit', '贏錢離場 (≥ 1.0)', 168849, 25.51);

INSERT INTO churn_last_days VALUES ('101003', 1, 402798, 1.032, 653.74, 77.36);
INSERT INTO churn_last_days VALUES ('101003', 2, 129124, 1.3121, 310.21, 75.94);
INSERT INTO churn_last_days VALUES ('101003', 3, 67219, 1.4027, 338.58, 75.57);
INSERT INTO churn_last_days VALUES ('102003', 1, 661983, 1.3875, 915.86, 74.49);
INSERT INTO churn_last_days VALUES ('102003', 2, 164585, 1.7118, 399.44, 71.81);
INSERT INTO churn_last_days VALUES ('102003', 3, 57483, 2.4942, 495.58, 68.14);
