/** Node identity selects the reference-role compiler without changing saved state. */
export const PROFILE = Object.freeze({
  nodeType: 'Krea2CharacterSheetDesigner',
  displayName: 'Krea2 Character Sheet Designer',
  extensionName: 'krea2.CharacterSheetDesigner',
  previewPath: '/krea2_character_sheet_designer/preview',
});
export const LAYOUT_PROFILE = Object.freeze({
  ...PROFILE,
  nodeType: 'Krea2LayoutReferenceSheetDesigner',
  displayName: 'Krea2 Layout Reference Sheet Designer (Experimental)',
  previewPath: '/krea2_character_sheet_designer/layout-reference/preview',
});
export const PROFILES = Object.freeze([PROFILE, LAYOUT_PROFILE]);
export function profileFor(node) {
  return PROFILES.find(p => p.nodeType === node.comfyClass || p.nodeType === node.type);
}
