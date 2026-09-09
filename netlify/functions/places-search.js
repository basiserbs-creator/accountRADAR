const { getSession } = require('./_auth');

exports.handler = async (event) => {
  const session = getSession(event);
  if (!session) {
    return {
      statusCode: 401,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ error: 'Niet ingelogd.' })
    };
  }

  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: 'Method not allowed' };
  }

  const apiKey = process.env.GOOGLE_PLACES_API_KEY;
  if (!apiKey) {
    return {
      statusCode: 500,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ error: 'Server niet correct geconfigureerd (ontbrekende sleutel).' })
    };
  }

  let body;
  try {
    body = JSON.parse(event.body || '{}');
  } catch (e) {
    return { statusCode: 400, body: JSON.stringify({ error: 'Ongeldig verzoek.' }) };
  }

  const { textQuery, lat, lng, radiusMeters } = body;
  if (!textQuery || typeof lat !== 'number' || typeof lng !== 'number') {
    return { statusCode: 400, body: JSON.stringify({ error: 'Ontbrekende velden.' }) };
  }

  try {
    const res = await fetch('https://places.googleapis.com/v1/places:searchText', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': apiKey,
        'X-Goog-FieldMask': 'places.id,places.displayName,places.formattedAddress,places.location,places.websiteUri,places.internationalPhoneNumber'
      },
      body: JSON.stringify({
        textQuery: textQuery,
        languageCode: 'nl',
        locationBias: { circle: { center: { latitude: lat, longitude: lng }, radius: radiusMeters || 25000 } }
      })
    });
    const data = await res.json();
    if (!res.ok) {
      return {
        statusCode: res.status,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ error: 'Fout bij Google Places.', details: data })
      };
    }
    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    };
  } catch (e) {
    return {
      statusCode: 502,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ error: 'Kon Google Places niet bereiken.' })
    };
  }
};
