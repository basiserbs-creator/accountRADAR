const { getSession } = require('./_auth');
const { getUser, sweepExpiredReservations } = require('./_tokens');

exports.handler = async (event) => {
  const session = getSession(event);
  if (!session) {
    return { statusCode: 401, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Niet ingelogd.' }) };
  }

  await sweepExpiredReservations(session.username);
  const user = await getUser(session.username);
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
