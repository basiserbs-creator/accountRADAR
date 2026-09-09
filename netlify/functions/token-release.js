const { getSession } = require('./_auth');
const {
  getUser, saveUser,
  getReservation, saveReservation,
  loadReservationIndex, saveReservationIndex
} = require('./_tokens');

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
  if (!actionCode) {
    return { statusCode: 400, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Ontbrekend veld actionCode.' }) };
  }

  const username = session.username;
  const r = await getReservation(username, actionCode);
  if (!r || r.status !== 'gereserveerd') {
    const user = await getUser(username);
    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ok: true, alreadyProcessed: true, balance: user ? (user.billingMode === 'onbeperkt' ? null : user.balance) : null })
    };
  }

  const user = await getUser(username);
  if (user && user.billingMode !== 'onbeperkt') {
    user.balance = (user.balance || 0) + r.tokens;
    await saveUser(username, user);
  }

  r.status = 'vrijgegeven';
  r.releasedAt = Date.now();
  await saveReservation(username, actionCode, r);

  const idx = await loadReservationIndex(username);
  await saveReservationIndex(username, idx.filter((c) => c !== actionCode));

  return {
    statusCode: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ok: true, balance: user ? (user.billingMode === 'onbeperkt' ? null : user.balance) : null })
  };
};
