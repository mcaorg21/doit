// Walks a parsed JSON value (e.g. an HTTP Request's Result preview) and figures out
// which dot-paths (e.g. "address.geo.lat") can actually be referenced from a
// downstream field via {{prefix.path}} template syntax.
//
// A top-level array's elements represent one loop `item` each — the index isn't
// part of the reference (whichever element is currently being iterated), so
// descending into it doesn't add a path segment. A NESTED array can't be expressed
// at all by {{a.b.c}} (the codegen only supports dict-key lookups, never a numeric
// index), so paths inside one aren't offered, even though the JSON tree still shows
// its contents.
export function flattenJsonPaths(value: unknown): string[] {
  const paths: string[] = []
  const seen = new Set<string>()

  function walk(node: unknown, segments: string[], referenceable: boolean) {
    if (Array.isArray(node)) {
      const isTopLevel = segments.length === 0
      for (const el of node) {
        walk(el, segments, isTopLevel && referenceable)
      }
      return
    }
    if (node !== null && typeof node === 'object') {
      for (const [key, val] of Object.entries(node as Record<string, unknown>)) {
        walk(val, [...segments, key], referenceable)
      }
      return
    }
    if (referenceable && segments.length > 0) {
      const path = segments.join('.')
      if (!seen.has(path)) {
        seen.add(path)
        paths.push(path)
      }
    }
  }

  walk(value, [], true)
  return paths
}

// The prefix a node's downstream fields use to reference its output: "item" while
// looping automatically, otherwise whatever the Result Variable is named.
export function referencePrefix(params: Record<string, unknown>): string {
  const autoLoop = params.autoLoop !== false
  if (autoLoop) return 'item'
  const resultVar = typeof params.resultVar === 'string' ? params.resultVar.trim() : ''
  return resultVar || 'resultVar'
}
