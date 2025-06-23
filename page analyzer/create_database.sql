-- Drop database if exists and create new one
DROP DATABASE IF EXISTS pdf_analytics;
CREATE DATABASE pdf_analytics;
USE pdf_analytics;

-- Create admins table
CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Create pdfs table
CREATE TABLE IF NOT EXISTS pdfs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    unique_url VARCHAR(36) NOT NULL UNIQUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total_pages INT NOT NULL DEFAULT 0,
    permanent_delete BOOLEAN DEFAULT FALSE,
    deleted_at DATETIME DEFAULT NULL,
    INDEX idx_unique_url (unique_url),
    INDEX idx_created_at (created_at),
    INDEX idx_deleted_at (deleted_at)
);

-- Create url_mappings table
CREATE TABLE IF NOT EXISTS url_mappings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    original_url VARCHAR(36) NOT NULL,
    public_url VARCHAR(36) NOT NULL UNIQUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_used DATETIME,
    pdf_id INT NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    total_views INT NOT NULL DEFAULT 0,
    last_viewed_at DATETIME,
    FOREIGN KEY (pdf_id) REFERENCES pdfs(id) ON DELETE CASCADE,
    FOREIGN KEY (original_url) REFERENCES pdfs(unique_url) ON DELETE CASCADE,
    INDEX idx_public_url (public_url),
    INDEX idx_created_at (created_at)
);

-- Create viewing_sessions table
CREATE TABLE IF NOT EXISTS viewing_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(50) NOT NULL,
    pdf_id INT NOT NULL,
    public_url VARCHAR(36) NOT NULL,
    start_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_time DATETIME,
    total_duration FLOAT NOT NULL DEFAULT 0,
    total_pages INT NOT NULL DEFAULT 0,
    unique_pages INT NOT NULL DEFAULT 0,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    user_agent VARCHAR(255),
    ip_address VARCHAR(45),
    last_activity DATETIME,
    status ENUM('active', 'completed', 'abandoned') NOT NULL DEFAULT 'active',
    original_filename VARCHAR(255) NOT NULL,
    browser VARCHAR(100),
    device_type VARCHAR(50),
    operating_system VARCHAR(100),
    country VARCHAR(100),
    city VARCHAR(100),
    is_remote_view BOOLEAN NOT NULL DEFAULT FALSE,
    email VARCHAR(255),
    FOREIGN KEY (pdf_id) REFERENCES pdfs(id) ON DELETE CASCADE,
    FOREIGN KEY (public_url) REFERENCES url_mappings(public_url) ON DELETE CASCADE,
    INDEX idx_session_id (session_id),
    INDEX idx_start_time (start_time),
    INDEX idx_status (status)
);

-- Create page_views table
CREATE TABLE IF NOT EXISTS page_views (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    pdf_id INT NOT NULL,
    page_number INT NOT NULL DEFAULT 1,
    start_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_time DATETIME,
    duration FLOAT NOT NULL DEFAULT 0,
    scroll_depth FLOAT NOT NULL DEFAULT 0,
    zoom_level FLOAT NOT NULL DEFAULT 1.0,
    time_to_first_view FLOAT,
    is_complete BOOLEAN NOT NULL DEFAULT FALSE,
    original_filename VARCHAR(255) NOT NULL,
    view_count INT NOT NULL DEFAULT 1,
    last_viewed_at DATETIME,
    total_time_on_page FLOAT NOT NULL DEFAULT 0,
    max_scroll_depth FLOAT NOT NULL DEFAULT 0,
    max_zoom_level FLOAT NOT NULL DEFAULT 1.0,
    FOREIGN KEY (session_id) REFERENCES viewing_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (pdf_id) REFERENCES pdfs(id) ON DELETE CASCADE,
    INDEX idx_page_number (page_number),
    INDEX idx_start_time (start_time),
    INDEX idx_session_page (session_id, page_number)
);

-- Insert default admin user
INSERT INTO admins (username, password) VALUES ('admin', 'admin123'); 