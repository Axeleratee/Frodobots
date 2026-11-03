// Mock Supabase client for headless testing - localStorage-backed.
// Mirrors only what the app actually calls. Anything the app does not use is
// deliberately missing, so a new call shows up as a test failure rather than
// silently passing against a stub that is more permissive than the real thing.
(function () {
  const LS = window.localStorage;
  const KEY = {
    observations: '__mock_table',
    profiles: '__mock_profiles',
    reports: '__mock_reports',
    audit: '__mock_audit',
    options: '__mock_options',
    assignments: '__mock_assignments'
  };

  const read = k => { try { return JSON.parse(LS.getItem(k) || '[]'); } catch (e) { return []; } };
  const write = (k, v) => LS.setItem(k, JSON.stringify(v));
  const readObj = k => { try { return JSON.parse(LS.getItem(k) || '{}'); } catch (e) { return {}; } };

  function uuid() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
      const r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

  function matches(row, filters) {
    return filters.every(f => {
      if (f.op === 'is' && f.val === null) return row[f.col] === null || row[f.col] === undefined;
      return String(row[f.col]) === String(f.val);
    });
  }

  // Simulate a table that has not been created yet (SQL not run).
  function missing(table) {
    return LS.getItem('__mock_' + table + '_missing') === '1';
  }
  const missingErr = t => ({ message: 'relation "public.' + t + '" does not exist' });

  function makeBuilder(table) {
    const b = { table, op: null, payload: null, filters: [] };
    const thenable = {
      // .insert(...).select(...) must stay an insert - only set op when unset.
      select() { if (!b.op) b.op = 'select'; return thenable; },
      insert(p) { b.op = 'insert'; b.payload = p; return thenable; },
      update(p) { b.op = 'update'; b.payload = p; return thenable; },
      delete() { b.op = 'delete'; return thenable; },
      eq(col, val) { b.filters.push({ col, val, op: 'eq' }); return thenable; },
      is(col, val) { b.filters.push({ col, val, op: 'is' }); return thenable; },
      order() { return run(); },
      limit() { return run(); },
      single() { return run().then(r => ({ data: (r.data && r.data[0]) || null, error: r.error })); },
      maybeSingle() { return run().then(r => ({ data: (r.data && r.data[0]) || null, error: r.error })); },
      then(res, rej) { return run().then(res, rej); }
    };

    function run() {
      return new Promise(resolve => {
        if (missing(b.table)) return resolve({ data: null, error: missingErr(b.table) });
        const key = KEY[b.table];

        if (b.op === 'select') {
          if (b.table === 'profiles') {
            const p = readObj(KEY.profiles);
            const rows = Object.keys(p).map(k => Object.assign({ id: k }, p[k]));
            return resolve({ data: rows.filter(r => matches(r, b.filters)), error: null });
          }
          let rows = key ? read(key) : [];
          rows = rows.filter(r => matches(r, b.filters));
          if (b.table === 'reports' || b.table === 'audit') {
            rows = rows.slice().sort((x, y) =>
              String(y.created_at || '').localeCompare(String(x.created_at || '')));
          }
          if (b.table === 'options') {
            rows = rows.slice().sort((x, y) => (x.sort_order || 0) - (y.sort_order || 0));
          }
          return resolve({ data: rows, error: null });
        }

        if (b.table === 'profiles') {
          const p = readObj(KEY.profiles);
          if (b.op === 'update') {
            const id = (b.filters[0] || {}).val;
            if (p[id]) { Object.assign(p[id], b.payload); LS.setItem(KEY.profiles, JSON.stringify(p)); }
          }
          return resolve({ data: null, error: null });
        }

        const rows = read(key);
        if (b.op === 'insert') {
          const list = Array.isArray(b.payload) ? b.payload : [b.payload];
          const made = list.map(p => Object.assign({
            id: uuid(),
            created_at: new Date().toISOString(),
            created_by: (window.__mockSession && window.__mockSession.user.id) || null
          }, p));
          write(key, rows.concat(made));
          return resolve({ data: made, error: null });
        }
        if (b.op === 'update') {
          rows.forEach(r => { if (matches(r, b.filters)) Object.assign(r, b.payload); });
          write(key, rows);
          return resolve({ data: null, error: null });
        }
        if (b.op === 'delete') {
          write(key, rows.filter(r => !matches(r, b.filters)));
          return resolve({ data: null, error: null });
        }
        resolve({ data: null, error: null });
      });
    }
    return thenable;
  }

  const listeners = [];
  const fire = (evt, sess) => listeners.forEach(cb => { try { cb(evt, sess); } catch (e) {} });

  window.supabase = {
    createClient() {
      return {
        from: makeBuilder,

        // Postgres functions the app calls through PostgREST.
        async rpc(name) {
          if (name === 'team_members') {
            if (missing('team_members')) return { data: null, error: missingErr('team_members') };
            const p = readObj(KEY.profiles);
            const rows = Object.keys(p).map(id => ({
              id,
              username: String(p[id].email || p[id].name || '').split('@')[0] || p[id].name || '',
              role: p[id].role || 'viewer'
            })).sort((a, b) => a.username.localeCompare(b.username));
            return { data: rows, error: null };
          }
          return { data: null, error: { message: 'unknown function ' + name } };
        },

        auth: {
          getSession: async () => ({ data: { session: window.__mockSession || null }, error: null }),
          async signInWithPassword({ email }) {
            const p = readObj(KEY.profiles);
            const id = 'uid-' + email;
            if (!p[id]) return { data: null, error: { message: 'Invalid login credentials' } };
            window.__mockSession = { user: { id, email }, access_token: 'mock-token' };
            fire('SIGNED_IN', window.__mockSession);
            return { data: { session: window.__mockSession, user: window.__mockSession.user }, error: null };
          },
          async signOut() { window.__mockSession = null; fire('SIGNED_OUT', null); return { error: null }; },
          async updateUser() { return { data: {}, error: null }; },
          onAuthStateChange(cb) {
            listeners.push(cb);
            setTimeout(() => cb('INITIAL_SESSION', window.__mockSession || null), 0);
            return { data: { subscription: { unsubscribe() {} } } };
          }
        }
      };
    }
  };
})();
