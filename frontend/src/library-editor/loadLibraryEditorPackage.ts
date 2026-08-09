/**
 * Dynamic import helper — preferred entry when wiring Detail later.
 * Keeps the editor off the index/vendor shell until explicitly loaded.
 */
export async function loadLibraryEditorPackage() {
  return import('./index')
}

export type LibraryEditorPackage = Awaited<ReturnType<typeof loadLibraryEditorPackage>>
