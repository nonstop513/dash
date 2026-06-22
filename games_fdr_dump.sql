DROP TABLE IF EXISTS games;
CREATE TABLE games (
            game_id    TEXT PRIMARY KEY,
            date_from  TEXT,
            date_to    TEXT,
            has_wide   INTEGER DEFAULT 0,
            has_cohort INTEGER DEFAULT 0,
            has_fdr    INTEGER DEFAULT 0
        );

INSERT INTO games VALUES ('101003', '2025-12-07', '2026-03-18', 1, 1, 1);
INSERT INTO games VALUES ('101007', '2026-01-07', '2026-02-07', 1, 0, 1);
INSERT INTO games VALUES ('102003', '2026-02-26', '2026-03-18', 0, 1, 1);

DROP TABLE IF EXISTS fdr_overview;
CREATE TABLE fdr_overview (
            game_id        TEXT PRIMARY KEY,
            total_records  INTEGER,
            retained       INTEGER,
            not_retained   INTEGER,
            retention_pct  REAL,
            avg_spin_ret   REAL,
            avg_spin_not   REAL,
            med_spin_ret   REAL,
            med_spin_not   REAL,
            avg_rtp_ret    REAL,
            avg_rtp_not    REAL
        );

INSERT INTO fdr_overview VALUES ('101003', 569971, 57116, 512855, 10.02, 398.51, 172.67, 203.0, 91.0, 0.965, 0.8263);
INSERT INTO fdr_overview VALUES ('101007', 277778, 168800, 108978, 60.77, 271.09, 144.28, 89.0, 46.0, 0.7743, 0.7037);
INSERT INTO fdr_overview VALUES ('102003', 774156, 97499, 676657, 12.59, 353.78, 147.08, 197.0, 82.0, 0.9918, 0.7452);
DROP TABLE IF EXISTS fdr_segments;
CREATE TABLE fdr_segments (
            game_id        TEXT,
            seg_type       TEXT,
            seg_order      INTEGER,
            seg_label      TEXT,
            retained       INTEGER,
            not_retained   INTEGER,
            retention_pct  REAL,
            avg_rtp_ret    REAL,
            avg_rtp_not    REAL,
            PRIMARY KEY (game_id, seg_type, seg_label)
        );

INSERT INTO fdr_segments VALUES ('101003', 'spin', 0, '1-100', 17618, 273918, 6.04, 0.8345, 0.7474);
INSERT INTO fdr_segments VALUES ('101003', 'spin', 1, '101-500', 25885, 204552, 11.23, 1.0035, 0.8982);
INSERT INTO fdr_segments VALUES ('101003', 'spin', 2, '501-2000', 12253, 33019, 27.07, 1.0629, 1.0262);
INSERT INTO fdr_segments VALUES ('101003', 'spin', 3, '2001-10000', 1348, 1363, 49.72, 1.0425, 1.0347);
INSERT INTO fdr_segments VALUES ('101003', 'spin', 4, '10000+', 12, 3, 80.0, 1.0041, 1.0263);
INSERT INTO fdr_segments VALUES ('101003', 'rtp', 0, '<50%', 5770, 95004, 5.73, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101003', 'rtp', 1, '50-80%', 11717, 155567, 7.0, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101003', 'rtp', 2, '80-90%', 7415, 73122, 9.21, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101003', 'rtp', 3, '90-95%', 4415, 33297, 11.71, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101003', 'rtp', 4, '95-100%', 4581, 30256, 13.15, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101003', 'rtp', 5, '100-110%', 6612, 37442, 15.01, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101003', 'rtp', 6, '110-125%', 7446, 35579, 17.31, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101003', 'rtp', 7, '>125%', 9160, 52588, 14.83, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101007', 'spin', 0, '1-100', 88531, 70307, 55.74, 0.6165, 0.5864);
INSERT INTO fdr_segments VALUES ('101007', 'spin', 1, '101-500', 54478, 31289, 63.52, 0.9251, 0.9024);
INSERT INTO fdr_segments VALUES ('101007', 'spin', 2, '501-2000', 23015, 7072, 76.49, 0.996, 0.9783);
INSERT INTO fdr_segments VALUES ('101007', 'spin', 3, '2001-10000', 2751, 309, 89.9, 1.0099, 0.9942);
INSERT INTO fdr_segments VALUES ('101007', 'spin', 4, '10000+', 25, 1, 96.15, 0.9814, 1.0022);
INSERT INTO fdr_segments VALUES ('101007', 'rtp', 0, '<50%', 51952, 42823, 54.82, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101007', 'rtp', 1, '50-80%', 31960, 21406, 59.89, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101007', 'rtp', 2, '80-90%', 19489, 11169, 63.57, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101007', 'rtp', 3, '90-95%', 11158, 5683, 66.25, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101007', 'rtp', 4, '95-100%', 11090, 5418, 67.18, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101007', 'rtp', 5, '100-110%', 14279, 6375, 69.13, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101007', 'rtp', 6, '110-125%', 12313, 5742, 68.2, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101007', 'rtp', 7, '>125%', 16559, 10362, 61.51, NULL, NULL);
INSERT INTO fdr_segments VALUES ('102003', 'spin', 0, '1-100', 28563, 376070, 7.06, 0.8781, 0.6577);
INSERT INTO fdr_segments VALUES ('102003', 'spin', 1, '101-500', 49361, 271358, 15.39, 1.0054, 0.8391);
INSERT INTO fdr_segments VALUES ('102003', 'spin', 2, '501-2000', 17967, 28350, 38.79, 1.1266, 0.9994);
INSERT INTO fdr_segments VALUES ('102003', 'spin', 3, '2001-10000', 1605, 877, 64.67, 1.086, 1.0271);
INSERT INTO fdr_segments VALUES ('102003', 'spin', 4, '10000+', 3, 2, 60.0, 1.0222, 1.011);
INSERT INTO fdr_segments VALUES ('102003', 'rtp', 0, '<50%', 25752, 304862, 7.79, NULL, NULL);
INSERT INTO fdr_segments VALUES ('102003', 'rtp', 1, '50-80%', 17521, 138065, 11.26, NULL, NULL);
INSERT INTO fdr_segments VALUES ('102003', 'rtp', 2, '80-90%', 7345, 41945, 14.9, NULL, NULL);
INSERT INTO fdr_segments VALUES ('102003', 'rtp', 3, '90-95%', 3953, 18253, 17.8, NULL, NULL);
INSERT INTO fdr_segments VALUES ('102003', 'rtp', 4, '95-100%', 3808, 17603, 17.79, NULL, NULL);
INSERT INTO fdr_segments VALUES ('102003', 'rtp', 5, '100-110%', 6245, 26326, 19.17, NULL, NULL);
INSERT INTO fdr_segments VALUES ('102003', 'rtp', 6, '110-125%', 8530, 30929, 21.62, NULL, NULL);
INSERT INTO fdr_segments VALUES ('102003', 'rtp', 7, '>125%', 24345, 98674, 19.79, NULL, NULL);