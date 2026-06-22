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

INSERT INTO fdr_overview VALUES ('101003', 445385, 258662, 186723, 58.08, 230.11, 143.71, 102.0, 71.0, 0.827, 0.7895);
INSERT INTO fdr_overview VALUES ('101007', 286726, 168800, 117926, 58.87, 271.09, 147.4, 89.0, 46.0, 0.7743, 0.7006);
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

INSERT INTO fdr_segments VALUES ('101003', 'spin', 0, '1-100', 128545, 111591, 53.53, 0.7063, 0.7068);
INSERT INTO fdr_segments VALUES ('101003', 'spin', 1, '101-500', 100045, 65189, 60.55, 0.9229, 0.9018);
INSERT INTO fdr_segments VALUES ('101003', 'spin', 2, '501-2000', 27760, 9656, 74.19, 1.023, 0.9812);
INSERT INTO fdr_segments VALUES ('101003', 'spin', 3, '2001-10000', 2301, 287, 88.91, 1.0318, 0.9956);
INSERT INTO fdr_segments VALUES ('101003', 'spin', 4, '10000+', 11, 0, 100.0, 1.0049, NULL);
INSERT INTO fdr_segments VALUES ('101003', 'rtp', 0, '<50%', 61004, 52787, 53.61, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101003', 'rtp', 1, '50-80%', 60454, 46038, 56.77, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101003', 'rtp', 2, '80-90%', 33919, 23047, 59.54, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101003', 'rtp', 3, '90-95%', 17549, 10857, 61.78, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101003', 'rtp', 4, '95-100%', 16129, 9696, 62.45, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101003', 'rtp', 5, '100-110%', 20330, 12198, 62.5, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101003', 'rtp', 6, '110-125%', 20267, 11618, 63.56, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101003', 'rtp', 7, '>125%', 29010, 20482, 58.62, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101007', 'spin', 0, '1-100', 88531, 76005, 53.81, 0.6165, 0.5812);
INSERT INTO fdr_segments VALUES ('101007', 'spin', 1, '101-500', 54478, 33684, 61.79, 0.9251, 0.9021);
INSERT INTO fdr_segments VALUES ('101007', 'spin', 2, '501-2000', 23015, 7844, 74.58, 0.996, 0.9784);
INSERT INTO fdr_segments VALUES ('101007', 'spin', 3, '2001-10000', 2751, 391, 87.56, 1.0099, 0.9939);
INSERT INTO fdr_segments VALUES ('101007', 'spin', 4, '10000+', 25, 2, 92.59, 0.9814, 1.0071);
INSERT INTO fdr_segments VALUES ('101007', 'rtp', 0, '<50%', 51952, 46460, 52.79, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101007', 'rtp', 1, '50-80%', 31960, 23126, 58.02, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101007', 'rtp', 2, '80-90%', 19489, 12082, 61.73, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101007', 'rtp', 3, '90-95%', 11158, 6145, 64.49, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101007', 'rtp', 4, '95-100%', 11090, 5875, 65.37, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101007', 'rtp', 5, '100-110%', 14279, 6895, 67.44, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101007', 'rtp', 6, '110-125%', 12313, 6235, 66.38, NULL, NULL);
INSERT INTO fdr_segments VALUES ('101007', 'rtp', 7, '>125%', 16559, 11108, 59.85, NULL, NULL);