const { requireAdmin } = require('./_admin');
const { usersStore } = require('./_store');

async function listAllUsernames(store) {
  const result = await store.list();
  if (result && Array.isArray(result.blobs)) return result.blobs.map((b) => b.key);
  if (Array.isArray(result)) return result.map((b) => (typeof b === 'string' ? b : b.key));
  return [];
}

exports.handler = async (event) => {
  const session = await requireAdmin(event);
  if (!session) {
    return { statusCode: 403, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: 'Geen toegang.' }) };
  }

  const store = usersStore();
  const usernames = await listAllUsernames(store);

  const users = [];
  for (const username of usernames) {
    const json = await store.get(username);
    if (!json) continue;
    let u;
    try { u = JSON.parse(json); } catch (e) { continue; }
    users.push({
      username: username,
      klant: u.klant || null,
      isAdmin: u.isAdmin === true,
      active: u.active !== false,
      accountEnd: u.accountEnd || null,
      billingMode: u.billingMode || 'normaal',
      balance: u.billingMode === 'onbeperkt' ? null : (u.balance || 0),
      startBalance: u.startBalance != null ? u.startBalance : null,
      totalUsed: u.totalUsed || 0,
      lastLogin: u.lastLogin || null,
      failedAttempts: u.failedAttempts || 0,
      lockedUntil: u.lockedUntil || null
    });
  }

  users.sort((a, b) => (a.klant || '').localeCompare(b.klant || '') || a.username.localeCompare(b.username));

  return {
    statusCode: 200,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ users: users })
  };
};
