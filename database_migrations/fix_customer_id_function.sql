-- 修復 get_next_available_id() 函數
-- 問題：原函數錯誤地查詢 drivers 表來計算 customers 表的下一個ID
-- 解決：修改函數正確查詢 customers 表
-- 日期：2025-06-08
-- 影響：解決 customers 表主鍵衝突問題

CREATE OR REPLACE FUNCTION get_next_available_id() RETURNS INTEGER AS $$
DECLARE
    next_id INTEGER;
BEGIN
    -- 修復：查詢 customers 表而不是 drivers 表
    SELECT MIN(t1.id + 1) INTO next_id
    FROM customers t1
    WHERE NOT EXISTS (
        SELECT 1
        FROM customers t2
        WHERE t2.id = t1.id + 1
    );
    
    IF next_id IS NULL THEN
        SELECT COALESCE(MAX(id) + 1, 1) INTO next_id
        FROM customers;
    END IF;
    
    RETURN next_id;
END;
$$ LANGUAGE plpgsql;

-- 驗證函數修復
-- SELECT get_next_available_id() as next_available_customer_id; 