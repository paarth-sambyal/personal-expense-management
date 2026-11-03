-- Personal Expense & Budget Management System (MySQL 8.0+)
CREATE DATABASE IF NOT EXISTS personal_expense_db CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE personal_expense_db;

CREATE TABLE IF NOT EXISTS users (
  user_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(100) NOT NULL,
  email VARCHAR(190) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS categories (
  category_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT UNSIGNED NULL,
  category_name VARCHAR(60) NOT NULL,
  is_default BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT fk_categories_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  CONSTRAINT uq_category_owner_name UNIQUE (user_id, category_name),
  INDEX idx_category_owner (user_id, category_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS income (
  income_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT UNSIGNED NOT NULL,
  source VARCHAR(100) NOT NULL,
  amount DECIMAL(12,2) NOT NULL,
  income_date DATE NOT NULL,
  description VARCHAR(500) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_income_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  CONSTRAINT chk_income_amount CHECK (amount > 0),
  INDEX idx_income_user_date (user_id, income_date),
  INDEX idx_income_user_amount (user_id, amount)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS expenses (
  expense_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT UNSIGNED NOT NULL,
  category_id BIGINT UNSIGNED NOT NULL,
  amount DECIMAL(12,2) NOT NULL,
  expense_date DATE NOT NULL,
  description VARCHAR(500) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_expense_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_expense_category FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE RESTRICT,
  CONSTRAINT chk_expense_amount CHECK (amount > 0),
  INDEX idx_expense_user_date (user_id, expense_date),
  INDEX idx_expense_user_category_date (user_id, category_id, expense_date),
  INDEX idx_expense_user_amount (user_id, amount)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS budgets (
  budget_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT UNSIGNED NOT NULL,
  category_id BIGINT UNSIGNED NULL,
  budget_month DATE NOT NULL,
  amount DECIMAL(12,2) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_budget_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_budget_category FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE CASCADE,
  CONSTRAINT chk_budget_first_day CHECK (DAY(budget_month) = 1),
  CONSTRAINT chk_budget_amount CHECK (amount > 0),
  INDEX idx_budget_user_month (user_id, budget_month)
) ENGINE=InnoDB;

-- Category NULL means overall monthly budget. MySQL permits multiple NULLs in a unique key,
-- so a generated sentinel key enforces one overall budget per owner/month.
ALTER TABLE budgets ADD COLUMN category_key BIGINT UNSIGNED GENERATED ALWAYS AS (IFNULL(category_id, 0)) STORED;
ALTER TABLE budgets ADD CONSTRAINT uq_budget_owner_scope_month UNIQUE (user_id, category_key, budget_month);

INSERT IGNORE INTO categories (user_id, category_name, is_default) VALUES
(NULL,'Food',TRUE),(NULL,'Transport',TRUE),(NULL,'Housing',TRUE),(NULL,'Utilities',TRUE),
(NULL,'Health',TRUE),(NULL,'Shopping',TRUE),(NULL,'Entertainment',TRUE),(NULL,'Education',TRUE),(NULL,'Other',TRUE);

-- Trigger verifies a category is global or belongs to the same user as its expense/budget.
DELIMITER $$
CREATE TRIGGER trg_expense_category_owner BEFORE INSERT ON expenses FOR EACH ROW
BEGIN
  IF NOT EXISTS (SELECT 1 FROM categories c WHERE c.category_id=NEW.category_id AND (c.user_id IS NULL OR c.user_id=NEW.user_id)) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Category is not available to this user';
  END IF;
END$$
CREATE TRIGGER trg_expense_category_owner_update BEFORE UPDATE ON expenses FOR EACH ROW
BEGIN
  IF NOT EXISTS (SELECT 1 FROM categories c WHERE c.category_id=NEW.category_id AND (c.user_id IS NULL OR c.user_id=NEW.user_id)) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Category is not available to this user';
  END IF;
END$$
CREATE TRIGGER trg_budget_category_owner BEFORE INSERT ON budgets FOR EACH ROW
BEGIN
  IF NEW.category_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM categories c WHERE c.category_id=NEW.category_id AND (c.user_id IS NULL OR c.user_id=NEW.user_id)) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Category is not available to this user';
  END IF;
END$$
CREATE PROCEDURE sp_monthly_totals(IN p_user_id BIGINT UNSIGNED, IN p_month DATE)
BEGIN
  SELECT COALESCE((SELECT SUM(amount) FROM income WHERE user_id=p_user_id AND income_date>=p_month AND income_date<DATE_ADD(p_month,INTERVAL 1 MONTH)),0) AS income_total,
         COALESCE((SELECT SUM(amount) FROM expenses WHERE user_id=p_user_id AND expense_date>=p_month AND expense_date<DATE_ADD(p_month,INTERVAL 1 MONTH)),0) AS expense_total;
END$$
DELIMITER ;

CREATE OR REPLACE VIEW monthly_summary AS
SELECT u.user_id, m.month_start,
       COALESCE(i.total,0) AS income, COALESCE(e.total,0) AS expenses
FROM users u
CROSS JOIN (SELECT DISTINCT DATE_SUB(DATE_FORMAT(income_date,'%Y-%m-01'),INTERVAL 0 DAY) month_start FROM income
            UNION SELECT DISTINCT DATE_FORMAT(expense_date,'%Y-%m-01') FROM expenses) m
LEFT JOIN (SELECT user_id,DATE_FORMAT(income_date,'%Y-%m-01') month_start,SUM(amount) total FROM income GROUP BY user_id,month_start) i
  ON i.user_id=u.user_id AND i.month_start=m.month_start
LEFT JOIN (SELECT user_id,DATE_FORMAT(expense_date,'%Y-%m-01') month_start,SUM(amount) total FROM expenses GROUP BY user_id,month_start) e
  ON e.user_id=u.user_id AND e.month_start=m.month_start;

-- Useful academic queries (run after creating an account and recording transactions):
-- 1. INNER JOIN: category expense totals
-- SELECT c.category_name,SUM(e.amount) total FROM expenses e JOIN categories c USING(category_id)
-- WHERE e.user_id=? GROUP BY c.category_id,c.category_name ORDER BY total DESC;
-- 2. LEFT JOIN: budgets including categories with zero spending
-- SELECT b.amount,COALESCE(SUM(e.amount),0) spent FROM budgets b LEFT JOIN expenses e
-- ON e.user_id=b.user_id AND e.expense_date>=b.budget_month AND e.expense_date<DATE_ADD(b.budget_month,INTERVAL 1 MONTH)
-- WHERE b.user_id=? GROUP BY b.budget_id;
-- 3. Aggregate functions and GROUP BY: SUM, AVG, COUNT
-- SELECT category_id,SUM(amount),AVG(amount),COUNT(*) FROM expenses WHERE user_id=? GROUP BY category_id;
-- 4. Subquery: expenses above the user's average transaction
-- SELECT * FROM expenses WHERE user_id=? AND amount>(SELECT AVG(amount) FROM expenses WHERE user_id=?);
-- 5. Stored procedure
-- CALL sp_monthly_totals(1,'2026-11-01');
-- 6. Transaction example (all-or-nothing multi-row update)
-- START TRANSACTION; UPDATE budgets SET amount=amount+100 WHERE budget_id=1; COMMIT;
