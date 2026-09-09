// Gedeelde login/sessie-helpers voor alle Netlify Functions.
// Wordt NIET los aangeroepen als endpoint (begint met _), alleen intern gebruikt.

const jwt = require('jsonwebtoken');

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

module.exports = { COOKIE_NAME, makeSessionCookie, clearSessionCookie, getSession };
