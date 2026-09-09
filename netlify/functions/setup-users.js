// EENMALIG gebruiken: open na deployen eenmaal in de browser
//   https://JOUW-SITE.netlify.app/.netlify/functions/setup-users?secret=JOUW_SETUP_SECRET
// om de testgebruikers aan te maken. Alleen bruikbaar met het juiste
// SETUP_SECRET (environment variable in Netlify), dus verder ongevaarlijk
// om te laten staan.

const bcrypt = require('bcryptjs');
const { usersStore } = require('./_store');

const TEST_USERS = [
  { username: 'testgebruiker1', password: 'Radar4721!', klant: 'Testklant', billingMode: 'onbeperkt' },
  { username: 'testgebruiker2', password: 'Kompas3098#', klant: 'Testklant', billingMode: 'normaal', startBalance: 250 },
  { username: 'testgebruiker3', password: 'Anker6650@', klant: 'Testklant', billingMode: 'normaal', startBalance: 250 }
];

exports.handler = async (event) => {
  const secret = event.queryStringParameters && event.queryStringParameters.secret;
  if (!secret || !process.env.SETUP_SECRET || secret !== process.env.SETUP_SECRET) {
    return { statusCode: 403, body: 'Verboden.' };
  }

  const store = usersStore();
  const created = [];

  for (const u of TEST_USERS) {
    const passwordHash = await bcrypt.hash(u.password, 12);
    await store.set(u.username, JSON.stringify({
      passwordHash: passwordHash,
      klant: u.klant,
      failedAttempts: 0,
      lockedUntil: null,
      lastLogin: null,
      billingMode: u.billingMode,
      balance: u.billingMode === 'normaal' ? u.startBalance : null,
      startBalance: u.billingMode === 'normaal' ? u.startBalance : null,
      totalUsed: 0
    }));
    created.push(u.username);
  }

  return {
    statusCode: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ok: true, created: created })
  };
};
