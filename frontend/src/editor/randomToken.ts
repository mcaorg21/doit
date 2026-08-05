// Used for any param field flagged `autoGenerate` (e.g. Webhook's Secret) — a short,
// URL-safe random token, generated client-side so a brand new node already has a
// usable value before it's ever saved.
export function genRandomToken(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID().replace(/-/g, '').slice(0, 24)
  }
  let token = ''
  for (let i = 0; i < 24; i++) token += Math.floor(Math.random() * 16).toString(16)
  return token
}
