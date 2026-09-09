// Accounteinddatum: actief tot en met 23:59:59 op de ingestelde datum, in
// tijdzone Europe/Amsterdam. In plaats van handmatige tijdzone-rekenkunde
// (foutgevoelig rond de zomer/wintertijd-overgang) vergelijken we de datum
// (YYYY-MM-DD) zoals die er in Amsterdam nu uitziet met de ingestelde
// einddatum - dat blijft correct zolang beide in hetzelfde ISO-formaat staan.

function amsterdamDateString(date) {
  // 'en-CA' geeft betrouwbaar YYYY-MM-DD terug.
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Amsterdam' }).format(date);
}

function isAccountExpired(accountEnd) {
  if (!accountEnd) return false; // geen einddatum ingesteld = blijft actief
  const todayAmsterdam = amsterdamDateString(new Date());
  return todayAmsterdam > accountEnd;
}

module.exports = { amsterdamDateString, isAccountExpired };
