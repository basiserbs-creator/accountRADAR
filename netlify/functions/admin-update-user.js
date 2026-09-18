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

  const store = usersStore();
  const json = await store.get(username);
  if (!json) {
    return { statusCode: 404, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Gebruiker niet gevonden.' }) };
  }
  const user = JSON.parse(json);

  // Alleen meegegeven velden aanpassen.
  if (body.billingMode === 'normaal' || body.billingMode === 'onbeperkt') {
    user.billingMode = body.billingMode;
    if (user.billingMode === 'onbeperkt') user.balance = null;
    else if (user.balance == null) user.balance = 0;
  }
  if (body.balance !== undefined && user.billingMode !== 'onbeperkt') {
    user.balance = Math.max(0, Number(body.balance) || 0);
  }
  if (body.startBalance !== undefined && user.billingMode !== 'onbeperkt') {
    user.startBalance = Math.max(0, Number(body.startBalance) || 0);
  }
  if (body.accountEnd !== undefined) {
    user.accountEnd = body.accountEnd ? String(body.accountEnd) : null;
  }
  if (body.active !== undefined) {
    user.active = body.active !== false;
  }
  if (body.klant !== undefined && String(body.klant).trim()) {
    user.klant = String(body.klant).trim();
  }

  await store.set(username, JSON.stringify(user));

  return {
    statusCode: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ok: true })
  };
};
