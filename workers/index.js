/**
 * Game Analytics API — Cloudflare Workers + D1
 *
 * This file mirrors api.py but runs on Cloudflare's edge network.
 * D1 uses the same SQL dialect as SQLite, so queries are identical.
 *
 * Setup:
 *   1. Create a D1 database:
 *        wrangler d1 create game-analytics
 *   2. Copy the database_id into wrangler.toml
 *   3. Import aggregated data:
 *        sqlite3 ../analytics.db .dump > analytics_dump.sql
 *        wrangler d1 execute game-analytics --file analytics_dump.sql
 *   4. Deploy:
 *        wrangler deploy
 */

const CORS = {
  "Content-Type": "application/json",
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: CORS });
}

function err(msg, status = 400) {
  return new Response(JSON.stringify({ error: msg }), { status, headers: CORS });
}

// ---------------------------------------------------------------------------
// Route handlers
// ---------------------------------------------------------------------------

async function handleGames(env) {
  const { results } = await env.DB.prepare(
    "SELECT * FROM games ORDER BY game_id"
  ).all();
  return json(results);
}

async function handleDomains(env, params) {
  const gameId = params.get("game_id");
  if (!gameId) return err("game_id required");

  const { results } = await env.DB.prepare(
    "SELECT domain FROM domains WHERE game_id = ? ORDER BY domain"
  ).bind(gameId).all();

  return json(results.map(r => r.domain));
}

async function handleDau(env, params) {
  const gameId = params.get("game_id");
  if (!gameId) return err("game_id required");

  const where  = ["game_id = ?"];
  const binds  = [gameId];

  const domain   = params.get("domain");
  const dateFrom = params.get("date_from");
  const dateTo   = params.get("date_to");

  if (domain && domain !== "ALL") { where.push("domain = ?");  binds.push(domain); }
  if (dateFrom)                   { where.push("date >= ?");   binds.push(dateFrom); }
  if (dateTo)                     { where.push("date <= ?");   binds.push(dateTo); }

  const sql = `
    SELECT date, domain, SUM(player_count) AS player_count
    FROM dau_daily
    WHERE ${where.join(" AND ")}
    GROUP BY date, domain
    ORDER BY date, domain
  `;
  const { results } = await env.DB.prepare(sql).bind(...binds).all();
  return json(results);
}

async function handleRtp(env, params) {
  const gameId = params.get("game_id");
  if (!gameId) return err("game_id required");

  const where = ["game_id = ?"];
  const binds = [gameId];

  const domain   = params.get("domain");
  const dateFrom = params.get("date_from");
  const dateTo   = params.get("date_to");

  if (domain && domain !== "ALL") { where.push("domain = ?"); binds.push(domain); }
  if (dateFrom)                   { where.push("date >= ?");  binds.push(dateFrom); }
  if (dateTo)                     { where.push("date <= ?");  binds.push(dateTo); }

  const sql = `
    SELECT
      date,
      AVG(avg_rtp)     AS avg_rtp,
      SUM(total_bet)   AS total_bet,
      AVG(avg_bet)     AS avg_bet,
      SUM(total_spins) AS total_spins
    FROM rtp_daily
    WHERE ${where.join(" AND ")}
    GROUP BY date
    ORDER BY date
  `;
  const { results } = await env.DB.prepare(sql).bind(...binds).all();
  return json(results);
}

async function handleCohort(env, params) {
  const gameId = params.get("game_id");
  if (!gameId) return err("game_id required");

  const maxDay = parseInt(params.get("max_day") ?? "30", 10);

  const { results } = await env.DB.prepare(`
    SELECT cohort_day, day_index, cohort_size, retention_rate
    FROM cohort_matrix
    WHERE game_id = ? AND day_index <= ?
    ORDER BY cohort_day, day_index
  `).bind(gameId, maxDay).all();

  return json(results);
}

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------

export default {
  async fetch(request, env) {
    const url    = new URL(request.url);
    const path   = url.pathname;
    const params = url.searchParams;

    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }

    if (request.method !== "GET") {
      return err("Method not allowed", 405);
    }

    try {
      if (path === "/api/games")   return await handleGames(env);
      if (path === "/api/domains") return await handleDomains(env, params);
      if (path === "/api/dau")     return await handleDau(env, params);
      if (path === "/api/rtp")     return await handleRtp(env, params);
      if (path === "/api/cohort")  return await handleCohort(env, params);

      return err("Not found", 404);
    } catch (e) {
      console.error(e);
      return err("Internal server error: " + e.message, 500);
    }
  },
};
