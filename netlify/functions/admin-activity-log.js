const { requireAdmin } = require('./_admin');
const { getActivityLog } = require('./_activity');

exports.handler = async (event) => {
  const session = await requireAdmin(event);
  if (!session) {
    return { statusCode: 403, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Geen toegang.' }) };
  }

  const limitParam = event.queryStringParameters && event.queryStringParameters.limit;
  const limit = Math.max(1, Math.min(500, parseInt(limitParam, 10) || 200));

  const log = await getActivityLog(limit);

  return {
    statusCode: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ log: log })
  };
};
