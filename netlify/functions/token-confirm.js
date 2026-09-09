const { getSession } = require('./_auth');
const {
  getUser, saveUser,
  getReservation, saveReservation,
  loadReservationIndex, saveReservationIndex
} = require('./_tokens');
const { logActivity } = require('./_activity');

exports.handler = async (event) => {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: 'Method not allowed' };
  }
  const session = getSession(event);
  if (!session) {
    return { statusCode: 401, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Niet ingelogd.' }) };
  }

  let body;
  try {
    body = JSON.parse(event.body || '{}');
  } catch (e) {
    return { statusCode: 400, body: JSON.stringify({ error: 'Ongeldig verzoek.' }) };
  }

  const actionCode = String(body.actionCode || '');
  const actualTokens = Number(body.actualTokens);

  if (!actionCode || !Number.isFinite(actualTokens) || actualTokens < 0) {
    return { statusCode: 400, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Ontbrekende of ongeldige velden.' }) };
  }

  const username = session.username;
  const r = await getReservation(username, actionCode);
  if (!r) {
    return { statusCode: 404, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Reservering niet gevonden (mogelijk al verwerkt of verlopen).' }) };
  }
  if (r.status !== 'gereserveerd') {
    return { statusCode: 200, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ok: true, alreadyProcessed: true }) };
  }

  const user = await getUser(username);
  if (!user) {
    return { statusCode: 404, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Gebruiker niet gevonden.' }) };
  }

  // Nooit meer afschrijven dan er gereserveerd was.
  const finalTokens = Math.min(actualTokens, r.tokens);

  if (user.billingMode !== 'onbeperkt') {
    const refund = r.tokens - finalTokens;
    user.balance = (user.balance || 0) + refund;
  }
  user.totalUsed = (user.totalUsed || 0) + finalTokens;
  await saveUser(username, user);

  r.status = 'afgeschreven';
  r.actualTokens = finalTokens;
  r.confirmedAt = Date.now();
  await saveReservation(username, actionCode, r);

  const idx = await loadReservationIndex(username);
  await saveReservationIndex(username, idx.filter((c) => c !== actionCode));

  await logActivity({ username: username, klant: user.klant || null, actionType: r.actionType, tokens: finalTokens });

  return {
    statusCode: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ok: true, balance: user.billingMode === 'onbeperkt' ? null : user.balance, charged: finalTokens })
  };
};
