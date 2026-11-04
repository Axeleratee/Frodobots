// Copy this file to config.js and fill in your own project's values.
// The anon / publishable key is meant to be public — it ships to every browser
// that opens the site, and your data is protected by Supabase RLS policies.
// NEVER put the service_role key here: it bypasses RLS.
window.APP_CONFIG = {
  SUPABASE_URL: 'https://YOUR-PROJECT.supabase.co',
  SUPABASE_ANON_KEY: 'YOUR-PUBLISHABLE-OR-ANON-KEY',
  LOGIN_EMAIL_DOMAIN: 'robotqa.local',

  // Days between an observation's date and the day it can actually be
  // reviewed (0 if your team reviews same-day).
  REVIEW_DELAY_DAYS: 2,

  // Days of the week with no shift (0 = Sunday). [] if you work every day.
  REST_DAYS: [0]
};
