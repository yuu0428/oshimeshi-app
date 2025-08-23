-- coupon_eventsテーブルにuser_idカラムを追加
-- 実行日: 2025-08-23

-- まず、coupon_eventsテーブルの構造を確認
-- \d coupon_events

-- user_idカラムが存在しない場合に追加
ALTER TABLE coupon_events 
ADD COLUMN IF NOT EXISTS user_id INTEGER;

-- 外部キー制約を追加（既存の場合はスキップされる）
DO $$ 
BEGIN
    -- user_idカラムに外部キー制約を追加（存在しない場合のみ）
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'coupon_events_user_id_fkey'
        AND table_name = 'coupon_events'
    ) THEN
        ALTER TABLE coupon_events 
        ADD CONSTRAINT coupon_events_user_id_fkey 
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
END $$;

-- インデックスを作成（既存の場合はスキップされる）
CREATE INDEX IF NOT EXISTS idx_coupon_events_user_id ON coupon_events(user_id);

-- 既存のレコードに対してuser_idを設定（必要に応じて）
-- 例: すべて管理者ユーザー(ID=1)に設定
UPDATE coupon_events 
SET user_id = 1 
WHERE user_id IS NULL;

-- user_idをNOT NULLに設定
ALTER TABLE coupon_events 
ALTER COLUMN user_id SET NOT NULL;