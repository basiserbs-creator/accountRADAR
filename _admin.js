const { getLiveSession } = require('./_auth');

// Geeft de sessie terug als het een geldige, ingelogde beheerder is,
// anders null. Gebruik: const session = await requireAdmin(event); if (!session) return 403;
async function requireAdmin(event) {
  const live = await getLiveSession(event);
  if (!live || live.session.isAdmin !== true) return null;
  return live.session;
}

function generatePassword() {
  const words = ['Radar', 'Blauw', 'Kompas', 'Anker', 'Beeld', 'Ruimte', 'Signaal', 'Punt', 'Kaart', 'Route'];
  const w = words[Math.floor(Math.random() * words.length)];
  const num = Math.floor(1000 + Math.random() * 9000);
  const sym = ['!', '#', '%', '@'][Math.floor(Math.random() * 4)];
  return w + num + sym;
}

module.exports = { requireAdmin, generatePassword };
