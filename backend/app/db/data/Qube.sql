CREATE DATABASE sonar CHARACTER SET utf8 COLLATE utf8_general_ci;
CREATE USER 'sonar'@'%' IDENTIFIED BY 'strong_password_here';
CREATE USER 'sonar'@'localhost' IDENTIFIED BY 'strong_password_here';
GRANT ALL PRIVILEGES ON sonar.* TO 'sonar'@'%';
GRANT ALL PRIVILEGES ON sonar.* TO 'sonar'@'localhost';
FLUSH PRIVILEGES;
