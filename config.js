// Project settings for this deployment.
// The anon / publishable key is public by design — it ships to every browser
// that opens the site, and the data is protected by Supabase RLS policies.
// Never put the service_role key here: it bypasses RLS.
window.APP_CONFIG = {
  SUPABASE_URL: 'https://xhjszkehyobzfxgdjhbn.supabase.co',
  SUPABASE_ANON_KEY: 'sb_publishable_uLpHY53WgmJ7RRSOFALgsQ_9rZmxJLd',
  LOGIN_EMAIL_DOMAIN: 'robotqa.local',

  // Days between an observation's date and the day your team can actually
  // review it. Raw footage lands, annotators work on it the next day, and the
  // cleaned result reaches QA the day after - so review is structurally two
  // days behind, and that delay is not the reviewers' doing. Nothing is
  // counted as missing, or as late, until it has actually arrived.
  REVIEW_DELAY_DAYS: 2,

  // Days of the week with no shift, so no review is expected and no gap is
  // reported. 0 = Sunday, 1 = Monday ... 6 = Saturday. Set to [] if the team
  // works every day.
  REST_DAYS: [0]
};
