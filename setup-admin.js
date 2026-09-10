// EENMALIG gebruiken: open na deployen eenmaal in de browser
//   https://JOUW-SITE.netlify.app/.netlify/functions/setup-admin?secret=JOUW_SETUP_SECRET
// om het beheeraccount aan te maken. Alleen bruikbaar met het juiste
// SETUP_SECRET (environment variable in Netlify).

const bcrypt = require('bcryptjs');
const { usersStore } = require('./_store');

const ADMIN_USERNAME = 'basiser';
const ADMIN_PASSWORD = 'brando-based-blocks-story';

exports.handler = async (event) => {
  const secret = event.queryStringParameters && event.queryStringParameters.secret;
  if (!secret || !process.env.SETUP_SECRET || secret !== process.env.SETUP_SECRET) {
    return { statusCode: 403, body: 'Verboden.' };
  }

  const store = usersStore();
  const passwordHash = await bcrypt.hash(ADMIN_PASSWORD, 12);

  await store.set(ADMIN_USERNAME, JSON.stringify({
    passwordHash: passwordHash,
    klant: 'Beheer',
    failedAttempts: 0,
    lockedUntil: null,
    lastLogin: null,
    billingMode: 'onbeperkt',
    balance: null,
    startBalance: null,
    totalUsed: 0,
    isAdmin: true,
    active: true,
    accountEnd: null
  }));

  return {
    statusCode: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ok: true, created: ADMIN_USERNAME })
  };
};
