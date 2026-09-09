const bcrypt = require('bcryptjs');
const { requireAdmin, generatePassword } = require('./_admin');
const { usersStore } = require('./_store');

exports.handler = async (event) => {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: 'Method not allowed' };
  }
  const session = requireAdmin(event);
  if (!session) {
    return { statusCode: 403, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Geen toegang.' }) };
  }

  let body;
  try {
    body = JSON.parse(event.body || '{}');
  } catch (e) {
    return { statusCode: 400, body: JSON.stringify({ error: 'Ongeldig verzoek.' }) };
  }

  const username = String(body.username || '').trim().toLowerCase();
  const klant = String(body.klant || '').trim();
  const billingMode = body.billingMode === 'onbeperkt' ? 'onbeperkt' : 'normaal';
  const startBalance = billingMode === 'normaal' ? Math.max(0, Number(body.startBalance) || 0) : null;
  const accountEnd = body.accountEnd ? String(body.accountEnd) : null; // 'YYYY-MM-DD' of null
  let password = String(body.password || '').trim();

  if (!username || !/^[a-z0-9._-]{3,40}$/.test(username)) {
    return { statusCode: 400, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Ongeldige gebruikersnaam (alleen letters, cijfers, punt, underscore of streepje, 3-40 tekens).' }) };
  }
  if (!klant) {
    return { statusCode: 400, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Klantnaam/klantcode is verplicht.' }) };
  }

  const store = usersStore();
  const existing = await store.get(username);
  if (existing) {
    return { statusCode: 409, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Deze gebruikersnaam bestaat al.' }) };
  }

  let generatedPassword = null;
  if (!password) {
    password = generatePassword();
    generatedPassword = password;
  }

  const passwordHash = await bcrypt.hash(password, 12);

  await store.set(username, JSON.stringify({
    passwordHash: passwordHash,
    klant: klant,
    failedAttempts: 0,
    lockedUntil: null,
    lastLogin: null,
    billingMode: billingMode,
    balance: startBalance,
    startBalance: startBalance,
    totalUsed: 0,
    isAdmin: false,
    active: true,
    accountEnd: accountEnd
  }));

  return {
    statusCode: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ok: true, username: username, generatedPassword: generatedPassword })
  };
};
