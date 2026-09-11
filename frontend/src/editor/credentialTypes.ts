// Most credential types are just "paste the API key" into one Value field — these
// need two secrets at once, so they get dedicated Login/Password inputs instead of
// making the user type a "login:password" string into a single field by hand. The
// two pieces are still packed into one "login:password" string for storage (the
// Credential model only has one Value field), just assembled here, not by the user.
// Shared between CredentialsManager (the full manager modal) and CredentialPickerField
// (the inline "+ New" quick-create shown next to a node's credential dropdown) so
// both agree on which credential types are pairs — see app/codegen/template_utils.py's
// resolve_credential_pair on the backend for the matching "login:password" parsing.
export const PAIR_TYPES = new Set(['2captcha_browser', 'login'])
