-- Extend case_object_type enum to support annotations

ALTER TYPE case_object_type ADD VALUE IF NOT EXISTS 'annotation';
