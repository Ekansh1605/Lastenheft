-- Migration: link audit_events to queries via a proper foreign key.
--
-- The Day 1 schema joined audit_events <-> queries by session_id (a soft link).
-- This adds a query_id column with FK + cascade so:
--   * DELETE FROM queries WHERE id = ? automatically removes related audit_events
--     (GDPR Art. 17 right-to-erasure does the right thing end-to-end)
--   * Replay can fetch audit_events for a specific query directly
--
-- Idempotent: safe to re-run.

ALTER TABLE audit_events
    ADD COLUMN IF NOT EXISTS query_id UUID REFERENCES queries(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_audit_events_query ON audit_events(query_id);
