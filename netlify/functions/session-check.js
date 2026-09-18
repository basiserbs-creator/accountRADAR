const { getLiveSession } = require('./_auth');

exports.handler = async (event) => {
  const live = await getLiveSession(event);
  if (!live) {
    return {
      statusCode: 401,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ loggedIn: false })
    };
  }
  return {
    statusCode: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ loggedIn: true, username: live.session.username, klant: live.session.klant || null, isAdmin: live.session.isAdmin === true })
  };
};
