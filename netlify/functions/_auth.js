// Gedeelde login/sessie-helpers voor alle Netlify Functions.
// Wordt NIET los aangeroepen als endpoint (begint met _), alleen intern gebruikt.

const jwt = require('jsonwebtoken');
const { usersStore } = require('./_store');
const { isAccountExpired } = require('./_accountdate');

const COOKIE_NAME = 'ar_session';
const SESSION_HOURS = 8;

function getSecret() {
  const secret = process.env.SESSION_SECRET;
  if (!secret) {
    throw new Error('SESSION_SECRET ontbreekt als environment variable.');
  }
  return secret;
}

function parseCookies(header) {
  const out = {};
  if (!header) return out;
  header.split(';').forEach((part) => {
    const idx = part.indexOf('=');
    if (idx === -1) return;
    const k = part.slice(0, idx).trim();
    const v = part.slice(idx + 1).trim();
    out[k] = decodeURIComponent(v);
  });
  return out;
}

function makeSessionCookie(payload) {
  const token = jwt.sign(payload, getSecret(), { expiresIn: SESSION_HOURS + 'h' });
  const maxAge = SESSION_HOURS * 3600;
  return COOKIE_NAME + '=' + token + '; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=' + maxAge;
}

function clearSessionCookie() {
  return COOKIE_NAME + '=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0';
}

// Alleen het inlogbewijs (JWT) zelf controleren - snel, geen Blobs-aanroep,
// maar houdt geen rekening met een nieuwere login elders of een
// tussentijdse blokkade.
function getSession(event) {
  const header = (event.headers && (event.headers.cookie || event.headers.Cookie)) || '';
  const cookies = parseCookies(header);
  const token = cookies[COOKIE_NAME];
  if (!token) return null;
  try {
    return jwt.verify(token, getSecret());
  } catch (e) {
    return null;
  }
}

// Volledige, "live" controle: geldig inlogbewijs, EN dit is nog steeds de
// meest recente login voor dit account (voor "1 actieve sessie per
// account"), EN het account is niet inmiddels geblokkeerd of verlopen.
// Kost één extra Blobs-leesactie per aanroep, bewust geaccepteerd omdat
// "1 sessie per account" niet zonder een live-controle kan werken: het hele
// punt is dat een nieuwere login elders een oudere sessie direct laat
// stoppen.
async function getLiveSession(event) {
  const session = getSession(event);
  if (!session) return null;

  const store = usersStore();
  const json = await store.get(session.username);
  if (!json) return null;
  let user;
  try { user = JSON.parse(json); } catch (e) { return null; }

  if (user.active === false) return null;
  if (isAccountExpired(user.accountEnd)) return null;
  if (!session.sessionId || session.sessionId !== user.currentSessionId) return null;

  return { session: session, user: user };
}

module.exports = { COOKIE_NAME, makeSessionCookie, clearSessionCookie, getSession, getLiveSession };
