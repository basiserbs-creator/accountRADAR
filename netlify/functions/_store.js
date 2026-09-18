// Gedeelde helper om de gebruikers-opslag (Netlify Blobs) te openen.
// Normaal detecteert @netlify/blobs de omgeving automatisch op een
// Netlify Function. Bij sommige sites/accounts lukt die automatische
// detectie niet (MissingBlobsEnvironmentError) — in dat geval configureren
// we de store expliciet met een Site ID + Personal Access Token, ingesteld
// als environment variables BLOBS_SITE_ID en BLOBS_TOKEN.

const { getStore } = require('@netlify/blobs');

function usersStore() {
  const siteID = process.env.BLOBS_SITE_ID;
  const token = process.env.BLOBS_TOKEN;
  if (siteID && token) {
    return getStore({ name: 'accountradar-users', siteID: siteID, token: token });
  }
  return getStore('accountradar-users');
}

module.exports = { usersStore };
