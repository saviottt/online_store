CREATE DATABASE online_store;
USE online_store;
CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role ENUM('buyer','seller') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    product_name VARCHAR(150) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    image VARCHAR(255),
    seller_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (seller_id) REFERENCES users(user_id)
        ON DELETE CASCADE
);

CREATE TABLE orders (
    order_id INT AUTO_INCREMENT PRIMARY KEY,
    buyer_id INT,
    product_id INT,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'Pending',
    FOREIGN KEY (buyer_id) REFERENCES users(user_id)
        ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
        ON DELETE CASCADE
);

INSERT INTO users (name, email, password, role)
VALUES ('Don Seller', 'seller@gmail.com', '1234', 'seller');

INSERT INTO users (name, email, password, role)
VALUES ('Don Buyer', 'buyer@gmail.com', '1234', 'buyer');

SELECT * FROM users;


SELECT * FROM products;


SELECT * FROM orders;

SELECT 
    o.order_id,
    u1.name AS buyer_name,
    p.product_name,
    u2.name AS seller_name,
    o.status,
    o.order_date
FROM orders o
JOIN users u1 ON o.buyer_id = u1.user_id
JOIN products p ON o.product_id = p.product_id
JOIN users u2 ON p.seller_id = u2.user_id;