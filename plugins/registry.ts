// plugins/registry.ts — re-exports PluginRegistry from core
// User-supplied IPlugin implementations go in sibling subdirectories:
//   plugins/[plugin-name]/index.ts
export { PluginRegistry } from '../core/registry.js'
