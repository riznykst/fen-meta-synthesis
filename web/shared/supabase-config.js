/**
 * Public runtime configuration for the Supabase-backed registry.
 *
 * The publishable (anon) key is safe to ship: on the database side it can
 * only SELECT `registry_public` (accepted knowledge) — never source documents,
 * proposals or decisions, and it has no write privileges. See
 * supabase/migrations/0002_rls_and_rpc.sql.
 *
 * The service-role key and the database password must never appear here.
 * Runtime overrides still win: ?supabase_url=…&supabase_anon_key=… or values
 * kept in localStorage (see web/shared/supabase.js).
 */
(function (global) {
  "use strict";
  global.FEN_SUPABASE_DEFAULT = {
    url: "https://inzlpgfpeoizsremgqdn.supabase.co",
    anonKey: "sb_publishable_8-iXX4r0GwHOJTqvoHAccQ_dYmjRSp6",
  };
})(typeof window !== "undefined" ? window : globalThis);
