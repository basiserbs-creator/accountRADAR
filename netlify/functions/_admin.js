const { getSession } = require('./_auth');

// Geeft de sessie terug als het een geldige, ingelogde beheerder is,
// anders null. Gebruik: const session = requireAdmin(event); if (!session) return 403;
function requireAdmin(event) {
  const session = getSession(event);
  if (!session || session.isAdmin !== true) return null;
  return session;
}

function generatePassword() {
  const words = ['Radar', 'Blauw', 'Kompas', 'Anker', 'Beeld', 'Ruimte', 'Signaal', 'Punt', 'Kaart', 'Route'];
  const w = words[Math.floor(Math.random() * words.length)];
  const num = Math.floor(1000 + Math.random() * 9000);
  const sym = ['!', '#', '%', '@'][Math.floor(Math.random() * 4)];
  return w + num + sym;
}

module.exports = { requireAdmin, generatePassword };
