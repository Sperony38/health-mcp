CREATE TABLE IF NOT EXISTS patients (
    id BIGINT NOT NULL AUTO_INCREMENT,
    owner_user_id VARCHAR(128) NOT NULL,
    owner_display_name VARCHAR(255) NULL,
    external_id VARCHAR(128) NOT NULL,
    full_name VARCHAR(255) NULL,
    sex VARCHAR(16) NULL,
    birth_date DATE NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY ix_patients_owner_user_id (owner_user_id),
    UNIQUE KEY uq_patients_owner_external_id (owner_user_id, external_id)
);

CREATE TABLE IF NOT EXISTS indicators (
    id BIGINT NOT NULL AUTO_INCREMENT,
    code VARCHAR(128) NOT NULL,
    name VARCHAR(255) NOT NULL,
    standard_system VARCHAR(32) NULL,
    standard_code VARCHAR(64) NULL,
    canonical_unit VARCHAR(64) NULL,
    description TEXT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_indicators_code (code),
    UNIQUE KEY uq_indicators_standard_identity (standard_system, standard_code)
);

CREATE TABLE IF NOT EXISTS indicator_reference_ranges (
    id BIGINT NOT NULL AUTO_INCREMENT,
    indicator_id BIGINT NOT NULL,
    sex VARCHAR(16) NULL,
    min_age_days INT NULL,
    max_age_days INT NULL,
    lower_bound DECIMAL(14, 4) NULL,
    upper_bound DECIMAL(14, 4) NULL,
    note VARCHAR(255) NULL,
    priority INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY ix_indicator_reference_ranges_indicator_id (indicator_id),
    CONSTRAINT fk_indicator_reference_ranges_indicator
        FOREIGN KEY (indicator_id) REFERENCES indicators (id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lab_reports (
    id BIGINT NOT NULL AUTO_INCREMENT,
    patient_id BIGINT NOT NULL,
    source_system VARCHAR(128) NULL,
    external_report_id VARCHAR(128) NULL,
    collected_at DATETIME NOT NULL,
    notes TEXT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY ix_lab_reports_patient_collected_at (patient_id, collected_at),
    UNIQUE KEY uq_lab_reports_patient_source_external (patient_id, source_system, external_report_id),
    CONSTRAINT fk_lab_reports_patient
        FOREIGN KEY (patient_id) REFERENCES patients (id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lab_results (
    id BIGINT NOT NULL AUTO_INCREMENT,
    report_id BIGINT NOT NULL,
    indicator_id BIGINT NOT NULL,
    source_name VARCHAR(255) NULL,
    raw_value VARCHAR(64) NULL,
    value_operator VARCHAR(8) NULL,
    measured_value DECIMAL(14, 4) NOT NULL,
    unit VARCHAR(64) NULL,
    captured_lower_bound DECIMAL(14, 4) NULL,
    captured_upper_bound DECIMAL(14, 4) NULL,
    reference_text TEXT NULL,
    flag VARCHAR(32) NULL,
    comment TEXT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY ix_lab_results_indicator_id (indicator_id),
    KEY ix_lab_results_report_indicator (report_id, indicator_id),
    CONSTRAINT fk_lab_results_report
        FOREIGN KEY (report_id) REFERENCES lab_reports (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_lab_results_indicator
        FOREIGN KEY (indicator_id) REFERENCES indicators (id)
        ON DELETE RESTRICT
);
