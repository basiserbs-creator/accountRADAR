const { requireAdmin } = require('./_admin');
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
  if (!username) {
    return { statusCode: 400, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Gebruikersnaam ontbreekt.' }) };
  }
  if (username === session.username) {
    return { statusCode: 400, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Je kunt je eigen beheeraccount niet verwijderen.' }) };
  }

  const store = usersStore();
  const existing = await store.get(username);
  if (!existing) {
    return { statusCode: 404, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Gebruiker niet gevonden.' }) };
  }

  await store.delete(username);

  return {
    statusCode: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ok: true })
  };
};
