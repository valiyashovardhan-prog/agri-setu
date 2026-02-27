-- 1. Initialize Database
-- Drops the database if it exists to ensure a clean slate (Be careful with real data!)
DROP DATABASE IF EXISTS agri_setu_db;
CREATE DATABASE agri_setu_db;
USE agri_setu_db;

-- 2. Create Users Table (Farmers & Consumers)
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role ENUM('Farmer', 'Consumer') NOT NULL,
    phone VARCHAR(20) DEFAULT 'Not Provided',
    about_me TEXT,
    profile_pic VARCHAR(255) DEFAULT 'default.png',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Create Marketplace Table (Inventory)
CREATE TABLE marketplace (
    id INT AUTO_INCREMENT PRIMARY KEY,
    farmer_id INT,
    item_name VARCHAR(100) NOT NULL,
    category ENUM('Grain', 'Veg', 'Fruit', 'Waste') NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    stock INT NOT NULL,
    description TEXT,
    image_file VARCHAR(255) DEFAULT NULL,
    qr_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (farmer_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 4. Create Orders Table (Transaction History)
CREATE TABLE orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    buyer_id INT,
    farmer_id INT,
    item_name VARCHAR(100),
    quantity INT,
    total_price DECIMAL(10, 2),
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (buyer_id) REFERENCES users(id),
    FOREIGN KEY (farmer_id) REFERENCES users(id)
);

-- 5. Messages Table (Real-Time Chat)
CREATE TABLE messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sender_id INT,
    receiver_id INT,
    message TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES users(id),
    FOREIGN KEY (receiver_id) REFERENCES users(id)
);

-- 6. Create Notifications Table (Real-time Alerts)
CREATE TABLE notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT, 
    message TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 7. Create Reviews Table (Ratings System)
CREATE TABLE reviews (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT,
    farmer_id INT,
    buyer_id INT,
    rating INT CHECK (rating >= 1 AND rating <= 5),
    review_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (farmer_id) REFERENCES users(id),
    FOREIGN KEY (buyer_id) REFERENCES users(id)
);
