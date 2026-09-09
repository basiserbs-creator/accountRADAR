const { getSession } = require('./_auth');
const {
  getUser, saveUser, sweepExpiredReservations,
  loadReservationIndex, saveReservationIndex,
  getReservation, saveReservation, RESERVATION_TTL_MS
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
  const actionType = String(body.actionType || '');
  const tokens = Number(body.tokens);

  if (!actionCode || !actionType || !Number.isFinite(tokens) || tokens < 0) {
    return { statusCode: 400, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Ontbrekende of ongeldige velden.' }) };
  }

  const username = session.username;
  await sweepExpiredReservations(username);

  // Dezelfde actiecode nooit tweemaal verwerken (voorkomt dubbele afschrijving
  // bij dubbelklikken of een opnieuw verstuurd verzoek).
  const existing = await getReservation(username, actionCode);
  if (existing) {
    return { statusCode: 200, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ok: true, alreadyReserved: true }) };
  }

  const user = await getUser(username);
  if (!user) {
    return { statusCode: 404, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Gebruiker niet gevonden.' }) };
  }

  if (user.billingMode !== 'onbeperkt') {
    const balance = user.balance || 0;
    if (balance < tokens) {
      return {
        statusCode: 402,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ error: 'Onvoldoende saldo voor deze actie.', balance: balance, nodig: tokens })
      };
    }
    user.balance = balance - tokens;
    await saveUser(username, user);
  }

  const now = Date.now();
  await saveReservation(username, actionCode, {
    actionType: actionType,
    tokens: tokens,
    status: 'gereserveerd',
    createdAt: now,
    expiresAt: now + RESERVATION_TTL_MS
  });

  const idx = await loadReservationIndex(username);
  idx.push(actionCode);
  await saveReservationIndex(username, idx);

  return {
    statusCode: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ok: true, balance: user.billingMode === 'onbeperkt' ? null : user.balance })
  };
};
