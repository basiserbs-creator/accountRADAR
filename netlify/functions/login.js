const bcrypt = require('bcryptjs');
const { usersStore } = require('./_store');
const { makeSessionCookie } = require('./_auth');

const MAX_ATTEMPTS = 3;
const LOCKOUT_MINUTES = 10;
const GENERIC_ERROR = { error: 'Onjuiste gebruikersnaam of wachtwoord.' };

exports.handler = async (event) => {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: 'Method not allowed' };
  }

  let body;
  try {
    body = JSON.parse(event.body || '{}');
  } catch (e) {
    return { statusCode: 400, body: JSON.stringify({ error: 'Ongeldig verzoek.' }) };
  }

  const username = String(body.username || '').trim().toLowerCase();
  const password = String(body.password || '');

  if (!username || !password) {
    return { statusCode: 400, body: JSON.stringify({ error: 'Gebruikersnaam en wachtwoord zijn verplicht.' }) };
  }

  const store = usersStore();
  const userJson = await store.get(username);

  if (!userJson) {
    // zelfde generieke foutmelding als bij fout wachtwoord, zodat niet zichtbaar
    // wordt of een gebruikersnaam bestaat
    return { statusCode: 401, body: JSON.stringify(GENERIC_ERROR) };
  }

  let user;
  try {
    user = JSON.parse(userJson);
  } catch (e) {
    return { statusCode: 401, body: JSON.stringify(GENERIC_ERROR) };
  }

  if (user.lockedUntil && Date.now() < user.lockedUntil) {
    const minsLeft = Math.max(1, Math.ceil((user.lockedUntil - Date.now()) / 60000));
    return {
      statusCode: 423,
      body: JSON.stringify({ error: 'Te veel mislukte pogingen. Probeer over ' + minsLeft + ' minuten opnieuw.' })
    };
  }

  const ok = await bcrypt.compare(password, user.passwordHash);

  if (!ok) {
    user.failedAttempts = (user.failedAttempts || 0) + 1;
    if (user.failedAttempts >= MAX_ATTEMPTS) {
      user.lockedUntil = Date.now() + LOCKOUT_MINUTES * 60000;
      user.failedAttempts = 0;
    }
    await store.set(username, JSON.stringify(user));
    return { statusCode: 401, body: JSON.stringify(GENERIC_ERROR) };
  }

  user.failedAttempts = 0;
  user.lockedUntil = null;
  user.lastLogin = Date.now();
  await store.set(username, JSON.stringify(user));

  const cookie = makeSessionCookie({ username: username, klant: user.klant || null });

  return {
    statusCode: 200,
    headers: { 'Set-Cookie': cookie, 'Content-Type': 'application/json' },
    body: JSON.stringify({ ok: true, username: username, klant: user.klant || null })
  };
};
