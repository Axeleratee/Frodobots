// Project settings for this deployment.
// The anon / publishable key is public by design — it ships to every browser
// that opens the site, and the data is protected by Supabase RLS policies.
// Never put the service_role key here: it bypasses RLS.
window.APP_CONFIG = {
  SUPABASE_URL: 'https://xhjszkehyobzfxgdjhbn.supabase.co',
  SUPABASE_ANON_KEY: 'sb_publishable_uLpHY53WgmJ7RRSOFALgsQ_9rZmxJLd',
  LOGIN_EMAIL_DOMAIN: 'robotqa.local'
};
