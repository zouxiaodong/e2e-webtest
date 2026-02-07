-- 创建数据库
CREATE DATABASE IF NOT EXISTS e2e_test_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 授权用户访问
GRANT ALL PRIVILEGES ON e2e_test_db.* TO 'e2e'@'%';
FLUSH PRIVILEGES;