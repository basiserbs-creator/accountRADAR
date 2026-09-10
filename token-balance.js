const { getLiveSession } = require('./_auth');
const { sweepExpiredReservations, getUser } = require('./_tokens');

exports.handler = async (event) => {
  const live = await getLiveSession(event);
  if (!live) {
    return { statusCode: 401, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Niet ingelogd.' }) };
  }

  await sweepExpiredReservations(live.session.username);
  // sweepExpiredReservations kan het saldo net hebben aangepast - vers ophalen.
  const user = await getUser(live.session.username);
  if (!user) {
    return { statusCode: 404, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Gebruiker niet gevonden.' }) };
  }

  return {
    statusCode: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      billingMode: user.billingMode || 'normaal',
      balance: user.billingMode === 'onbeperkt' ? null : (user.balance || 0),
      totalUsed: user.totalUsed || 0
    })
  };
};
