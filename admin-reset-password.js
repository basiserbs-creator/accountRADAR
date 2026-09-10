const bcrypt = require('bcryptjs');
const { requireAdmin, generatePassword } = require('./_admin');
const { usersStore } = require('./_store');

exports.handler = async (event) => {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: 'Method not allowed' };
  }
  const session = await requireAdmin(event);
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
  let newPassword = String(body.newPassword || '').trim();

  if (!username) {
    return { statusCode: 400, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Gebruikersnaam ontbreekt.' }) };
  }

  const store = usersStore();
  const json = await store.get(username);
  if (!json) {
    return { statusCode: 404, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Gebruiker niet gevonden.' }) };
  }
  const user = JSON.parse(json);

  let generatedPassword = null;
  if (!newPassword) {
    newPassword = generatePassword();
    generatedPassword = newPassword;
  }

  user.passwordHash = await bcrypt.hash(newPassword, 12);
  user.failedAttempts = 0;
  user.lockedUntil = null;
  // Bewuste keuze (zie overleg): een reset maakt bestaande sessies niet
  // direct ongeldig - die lopen door tot ze zelf verlopen of de gebruiker
  // opnieuw inlogt. Voor deze schaal (kleine, vertrouwde groep) is dat
  // voldoende; zie NETLIFY_INSTRUCTIES.md voor de afweging.
  await store.set(username, JSON.stringify(user));

  return {
    statusCode: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ok: true, generatedPassword: generatedPassword })
  };
};
