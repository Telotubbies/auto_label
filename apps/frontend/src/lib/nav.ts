/**
 * Nav v2 information architecture, kept free of React so the role matrix stays unit-testable.
 * Groups live one per feature under `nav/`; this module is the stable import surface.
 * Routes that were renamed keep a redirect in the route registry via LEGACY_PROJECT_PATHS.
 *
 * Relative imports carry the `.ts` extension because `tests/nav.test.mjs` executes this module
 * directly with Node's type stripping, which resolves specifiers literally.
 */
export * from './nav/types.ts'
export * from './nav/audience.ts'
export * from './nav/registry.ts'
export * from './nav/visibility.ts'
