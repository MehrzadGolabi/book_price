CREATE DATABASE IF NOT EXISTS book_publishing CHARACTER SET utf8mb4 COLLATE utf8mb4_persian_ci;
USE book_publishing;

-- Table to store the dynamic "Types" (نوع)
CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL, -- e.g., "نوع کاغذ متن"
    item_value VARCHAR(255) NOT NULL,    -- e.g., "ايندربورد 200 گرم"
    UNIQUE(category_name, item_value)
);

-- Table to store the paper preprocessing calculations
CREATE TABLE IF NOT EXISTS paper_calculations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    paper_type VARCHAR(255) NOT NULL,
    formula_type VARCHAR(100) NOT NULL,
    weight DECIMAL(15,2),
    height DECIMAL(15,2),
    length DECIMAL(15,2),
    bundle_count INT,
    bundle_weight DECIMAL(15,2),
    price DECIMAL(15,2),
    unit_price DECIMAL(15,2)
);

-- Table to store the main project details
CREATE TABLE IF NOT EXISTS projects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    subtitle VARCHAR(255),
    creation_date DATE NOT NULL,
    qate VARCHAR(100), -- قطع
    tiraj INT NOT NULL, -- تیراژ
    nobat_chap INT,
    tedad_onvan INT,
    tedad_safeh INT,
    shomaregan INT,
    qad_ketab VARCHAR(100),
    abaad_jeld VARCHAR(100),
    royalty_percent DECIMAL(5,2), -- حق تالیف درصدی
    total_cost DECIMAL(15,2),
    single_book_cost DECIMAL(15,2)
);

-- Table to store the specific costs and selections for a project
CREATE TABLE IF NOT EXISTS project_details (
    project_id INT PRIMARY KEY,
    -- Types (نوع)
    noeh_kaghaz_matn VARCHAR(255),
    noeh_chap_matn VARCHAR(255),
    noeh_rang_matn VARCHAR(255),
    noeh_zink_matn VARCHAR(255),
    noeh_kaghaz_jeld VARCHAR(255),
    noeh_chap_jeld VARCHAR(255),
    noeh_rang_jeld VARCHAR(255),
    noeh_zink_jeld VARCHAR(255),
    tedad_form_chap_matn INT,
    tedad_form_chap_jeld INT,
    hazineh_talif DECIMAL(15,2) DEFAULT 0,
    hazineh_tarjomeh DECIMAL(15,2) DEFAULT 0,
    hazineh_tasvir DECIMAL(15,2) DEFAULT 0,
    hazineh_virayesh DECIMAL(15,2) DEFAULT 0,
    hazineh_tarahi_jeld DECIMAL(15,2) DEFAULT 0,
    hazineh_modiriat_atelieh DECIMAL(15,2) DEFAULT 0,
    hazineh_zink DECIMAL(15,2) DEFAULT 0,
    hazineh_chap_matn DECIMAL(15,2) DEFAULT 0,
    hazineh_chap_jeld DECIMAL(15,2) DEFAULT 0,
    hazineh_kaghaz_matn DECIMAL(15,2) DEFAULT 0,
    hazineh_kaghaz_jeld DECIMAL(15,2) DEFAULT 0,
    hazineh_rokesh_salfon DECIMAL(15,2) DEFAULT 0,
    hazineh_moghava_maghzi DECIMAL(15,2) DEFAULT 0,
    hazineh_ghaleb_letterpress DECIMAL(15,2) DEFAULT 0,
    hazineh_ghaleb_diecut DECIMAL(15,2) DEFAULT 0,
    hazineh_khat_ta DECIMAL(15,2) DEFAULT 0,
    hazineh_malzomat DECIMAL(15,2) DEFAULT 0,
    hazineh_jeldsazi DECIMAL(15,2) DEFAULT 0,
    hazineh_sahafi DECIMAL(15,2) DEFAULT 0,
    hazineh_boresh_bastebandi DECIMAL(15,2) DEFAULT 0,
    hazineh_haml_naghl DECIMAL(15,2) DEFAULT 0,
    hazineh_montaj DECIMAL(15,2) DEFAULT 0,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);