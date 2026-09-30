// ============================================================
//  ADMIN USER MANAGEMENT - Supabase Edge Function (Deno)
// ============================================================
//  Lets an ADMIN create accounts, reset passwords, and delete
//  users from inside the app. Uses the SERVICE ROLE key, which is
//  auto-injected into Edge Functions and must NEVER be in the browser.
//
//  Deploy (dashboard editor or CLI), function name EXACTLY: admin-users
//    supabase functions deploy admin-users --no-verify-jwt
//  No secrets to set - SUPABASE_URL, SUPABASE_ANON_KEY and
//  SUPABASE_SERVICE_ROLE_KEY are provided automatically.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
function json(obj: unknown, status = 200): Response {
  return new Response(JSON.stringify(obj), { status, headers: { ...cors, "Content-Type": "application/json" } });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  const SUPABASE_URL = Deno.env.get("SUPABASE_URL");
  const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!SUPABASE_URL || !SERVICE_ROLE) return json({ error: "server_not_configured" }, 500);

  const token = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  if (!token) return json({ error: "unauthorized" }, 401);

  const admin = createClient(SUPABASE_URL, SERVICE_ROLE, { auth: { persistSession: false } });

  // Who is calling?
  let callerId = "";
  try {
    const { data, error } = await admin.auth.getUser(token);
    if (error || !data?.user) return json({ error: "unauthorized" }, 401);
    callerId = data.user.id;
  } catch (e) {
    return json({ error: "auth_check_failed", detail: String((e as Error)?.message || e) }, 502);
  }

  // Caller must be an admin.
  try {
    const { data: prof } = await admin.from("profiles").select("role").eq("id", callerId).single();
    if (!prof || prof.role !== "admin") return json({ error: "forbidden" }, 403);
  } catch (e) {
    return json({ error: "role_check_failed", detail: String((e as Error)?.message || e) }, 502);
  }

  let body: any;
  try { body = await req.json(); } catch { return json({ error: "invalid_json" }, 400); }
  const action = body.action;
  const validRole = (r: string) => r === "admin" || r === "editor" || r === "viewer";

  try {
    if (action === "create") {
      if (!body.email || !body.password) return json({ error: "missing_email_or_password" }, 400);
      const { data, error } = await admin.auth.admin.createUser({
        email: body.email, password: body.password, email_confirm: true,
      });
      if (error) throw error;
      const newId = data?.user?.id;
      if (newId && body.role && validRole(body.role)) {
        await admin.from("profiles").update({ role: body.role }).eq("id", newId);
      }
      return json({ ok: true, id: newId });
    }

    // Login activity for the User Performance page (real data from Supabase Auth).
    if (action === "activity") {
      const out: any[] = [];
      let page = 1;
      while (page <= 10) {
        const { data, error } = await admin.auth.admin.listUsers({ page, perPage: 200 });
        if (error) throw error;
        const users = data?.users || [];
        users.forEach((u: any) => {
          out.push({
            id: u.id,
            email: u.email || "",
            last_sign_in_at: u.last_sign_in_at || null,
            created_at: u.created_at || null,
          });
        });
        if (users.length < 200) break;
        page++;
      }
      return json({ ok: true, users: out });
    }

    if (action === "reset_password") {
      if (!body.id || !body.password) return json({ error: "missing_id_or_password" }, 400);
      const { error } = await admin.auth.admin.updateUserById(body.id, { password: body.password });
      if (error) throw error;
      // Force them to set their own password on next login.
      await admin.from("profiles").update({ must_change_password: true }).eq("id", body.id);
      return json({ ok: true });
    }

    if (action === "delete") {
      if (!body.id) return json({ error: "missing_id" }, 400);
      if (body.id === callerId) return json({ error: "cannot_delete_self" }, 400);
      const { error } = await admin.auth.admin.deleteUser(body.id);
      if (error) throw error;
      return json({ ok: true });
    }

    return json({ error: "unknown_action" }, 400);
  } catch (e) {
    return json({ error: "action_failed", detail: String((e as Error)?.message || e) }, 502);
  }
});
