const { getSession } = require('./_auth');

exports.handler = async (event) => {
  const session = getSession(event);
  if (!session) {
    return {
      statusCode: 401,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ loggedIn: false })
    };
  }
  return {
    statusCode: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ loggedIn: true, username: session.username, klant: session.klant || null })
  };
};
