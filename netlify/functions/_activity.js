// Activiteitenlog: bewaart uitsluitend metadata (wie, welke actie, wanneer,
// hoeveel credits) - nooit de inhoud van Excel-bestanden, zoekresultaten of
// exports. Bewust zo gekozen (AVG-vriendelijk), zie ook het oorspronkelijke
// beveiligingsdocument.
//
// Simpele opzet: één lijst (max. de laatste 500 regels) in één Blob-sleutel.
// Voor deze schaal (een paar klanten) ruim voldoende en veel simpeler dan
// losse sleutels per logregel bijhouden.

const { getStore } = require('@netlify/blobs');

function activityStore() {
  const siteID = process.env.BLOBS_SITE_ID;
  const token = process.env.BLOBS_TOKEN;
  if (siteID && token) {
    return getStore({ name: 'accountradar-activity', siteID: siteID, token: token });
  }
  return getStore('accountradar-activity');
}

const MAX_ENTRIES = 500;

async function logActivity(entry) {
  try {
    const store = activityStore();
    const json = await store.get('log');
    let log = json ? JSON.parse(json) : [];
    log.push(Object.assign({ timestamp: Date.now() }, entry));
    if (log.length > MAX_ENTRIES) log = log.slice(log.length - MAX_ENTRIES);
    await store.set('log', JSON.stringify(log));
  } catch (e) {
    // Loggen mag nooit de eigenlijke actie laten mislukken.
  }
}

async function getActivityLog(limit) {
  const store = activityStore();
  const json = await store.get('log');
  const log = json ? JSON.parse(json) : [];
  return log.slice(-1 * (limit || 200)).reverse();
}

module.exports = { logActivity, getActivityLog };
