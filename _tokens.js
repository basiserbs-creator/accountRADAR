// Gedeelde helpers voor het tokensysteem.
//
// BELANGRIJKE KANTTEKENING (bewust, voor deze schaal): saldo-updates
// gebeuren hier als eenvoudige "lees, pas aan, schrijf terug" — niet met
// een database-transactie. Bij een paar bekende gebruikers die zelden
// precies tegelijk klikken is de kans op een botsing verwaarloosbaar; bij
// veel gelijktijdige gebruikers zou dit met een "echte" database opnieuw
// bekeken moeten worden. Dit is een bewuste, pragmatische keuze, passend
// bij de rest van dit project.

const { getStore } = require('@netlify/blobs');

function storeFor(name) {
  const siteID = process.env.BLOBS_SITE_ID;
  const token = process.env.BLOBS_TOKEN;
  if (siteID && token) {
    return getStore({ name: name, siteID: siteID, token: token });
  }
  return getStore(name);
}

function usersStore() { return storeFor('accountradar-users'); }
function reservationsStore() { return storeFor('accountradar-reservations'); }

const RESERVATION_TTL_MS = 10 * 60 * 1000; // 10 minuten

async function getUser(username) {
  const json = await usersStore().get(username);
  return json ? JSON.parse(json) : null;
}

async function saveUser(username, user) {
  await usersStore().set(username, JSON.stringify(user));
}

function reservationKey(username, actionCode) {
  return username + ':' + actionCode;
}

async function loadReservationIndex(username) {
  const json = await reservationsStore().get('index:' + username);
  return json ? JSON.parse(json) : [];
}

async function saveReservationIndex(username, idx) {
  await reservationsStore().set('index:' + username, JSON.stringify(idx));
}

async function getReservation(username, actionCode) {
  const json = await reservationsStore().get(reservationKey(username, actionCode));
  return json ? JSON.parse(json) : null;
}

async function saveReservation(username, actionCode, r) {
  await reservationsStore().set(reservationKey(username, actionCode), JSON.stringify(r));
}

// Best-effort: geeft verlopen, niet-afgeronde reserveringen van deze
// gebruiker vrij (ouder dan 10 minuten). In plaats van een geplande
// achtergrondtaak controleren we dit telkens wanneer het saldo wordt
// opgevraagd of een nieuwe reservering wordt aangevraagd.
async function sweepExpiredReservations(username) {
  const idx = await loadReservationIndex(username);
  if (!idx.length) return;

  const now = Date.now();
  const stillOpen = [];
  let user = null;

  for (const actionCode of idx) {
    const r = await getReservation(username, actionCode);
    if (!r || r.status !== 'gereserveerd') continue;
    if (now > r.expiresAt) {
      if (!user) user = await getUser(username);
      if (user && user.billingMode !== 'onbeperkt') {
        user.balance = (user.balance || 0) + r.tokens;
      }
      r.status = 'vrijgegeven';
      r.releasedAt = now;
      await saveReservation(username, actionCode, r);
    } else {
      stillOpen.push(actionCode);
    }
  }

  if (user) await saveUser(username, user);
  await saveReservationIndex(username, stillOpen);
}

module.exports = {
  getUser, saveUser,
  loadReservationIndex, saveReservationIndex,
  getReservation, saveReservation,
  sweepExpiredReservations,
  RESERVATION_TTL_MS
};
