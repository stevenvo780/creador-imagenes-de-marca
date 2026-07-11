-- Migración: Agregar columna logo_asset a tabla brands
-- Idempotente: no falla si la columna ya existe

-- SQLite
-- Ejecutar si DATABASE_URL es SQLite:
ALTER TABLE brands ADD COLUMN logo_asset TEXT;

-- Postgres
-- Ejecutar si DATABASE_URL es Postgres (reemplaza <schema> por el schema real):
-- ALTER TABLE public.brands ADD COLUMN IF NOT EXISTS logo_asset TEXT;
